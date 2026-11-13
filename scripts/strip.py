"""Remove the modules a project does not use (`make strip`).

    python -m scripts.strip                  # what would go, by the flags in .env
    python -m scripts.strip files tasks      # name the modules instead
    python -m scripts.strip --apply          # remove (asks first; --yes does not)

A module goes when its flag is off (AUTH_ENABLED, ADMIN_ENABLED, FILES_ENABLED,
NOTIFICATIONS_ENABLED, BACKGROUND_TASKS_ENABLED), together with the modules that need
it; `db` always stays. Removed: the packages, their entries in app/core/modules.py,
their requirements files, the tests marked with them (`pytest.mark.modules`), blocks
between `strip:begin <names>` and `strip:end` lines (compose services, CI jobs), and
openapi.json is written again. A new migration drops their tables. Settings in
app/config.py and .env.example stay: their defaults are harmless.

Runs only on a clean git working tree, so `git checkout . && git clean -fd` undoes it.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Requirements files that belong to one module; the others are shared
REQUIREMENTS = {"auth": "auth.txt", "files": "files.txt", "tasks": "tasks.txt"}
# Files of a kept module that only work with another one
EXTRA_FILES = {"tasks": ["app/modules/leads/tasks.py"]}
KEEP = {"db"}

MARKER = re.compile(r"strip:begin\s+(?P<names>[\w ]+)")
TEST_MARK = re.compile(r"^pytestmark = pytest\.mark\.modules\((?P<names>[^)]*)\)", re.M)

# Tables of the models of the given modules, in creation order; run in a separate
# process with fixed settings (importing models cannot be undone, and the local .env
# must not matter)
TABLES_SCRIPT = """
import json, sys
from importlib import import_module
from importlib.util import find_spec
from pathlib import Path
from app.core.modules import MODULES
from app.modules.db import Base
for spec in MODULES:
    if spec.name not in sys.argv[1:]:
        continue
    found = find_spec(spec.path)
    if found and found.origin and (Path(found.origin).parent / "models.py").exists():
        import_module(spec.path + ".models")
print(json.dumps([table.name for table in Base.metadata.sorted_tables]))
"""


def registry() -> list[dict]:
    from app.core.modules import MODULES

    return [{"name": s.name, "path": s.path, "requires": list(s.requires)} for s in MODULES]


def disabled_by_settings() -> set[str]:
    from app.config import Settings
    from app.core.modules import MODULES

    settings = Settings()
    return {spec.name for spec in MODULES if not spec.enabled(settings)}


def with_dependents(names: set[str], specs: list[dict]) -> set[str]:
    """The modules plus every module that needs one of them, `db` excepted."""
    removed = set(names) - KEEP
    while True:
        more = {s["name"] for s in specs if set(s["requires"]) & removed} - removed - KEEP
        if not more:
            return removed
        removed |= more


def package_dir(path: str) -> Path:
    return ROOT.joinpath(*path.split("."))


def remove_registry_entries(text: str, names: set[str]) -> str:
    for name in names:
        block = re.compile(r'\n    ModuleSpec\(\n        name="%s",\n.*?\n    \),' % re.escape(name), re.S)
        text, count = block.subn("", text)
        if count != 1:
            raise SystemExit(f"app/core/modules.py: no single ModuleSpec for {name!r}")
    return text


def remove_marked_blocks(text: str, names: set[str]) -> str:
    """Drop `strip:begin <names>` ... `strip:end` blocks naming a removed module (or
    `any`), marker lines included."""
    out: list[str] = []
    skipping = False
    for line in text.splitlines(keepends=True):
        if not skipping and (match := MARKER.search(line)):
            listed = set(match["names"].split())
            skipping = bool(listed & names or "any" in listed)
            if skipping:
                continue
        if skipping:
            if "strip:end" in line:
                skipping = False
            continue
        out.append(line)
    if skipping:
        raise SystemExit("strip:begin without strip:end")
    return "".join(out)


def without_requirement(text: str, filename: str) -> str:
    return re.sub(rf"^-r {re.escape(filename)}\n", "", text, flags=re.M)


def marked_tests(names: set[str]) -> list[Path]:
    found = []
    for path in sorted((ROOT / "tests").glob("test_*.py")):
        if match := TEST_MARK.search(path.read_text()):
            listed = set(re.findall(r'"(\w+)"', match["names"]))
            if listed & names:
                found.append(path)
    return found


# The minimal profile: importing the app package loads no module and no models
MINIMAL = {
    "APP_PROFILE": "minimal",
    "DATABASE_URL": "",
    "AUTH_ENABLED": "false",
    "ADMIN_ENABLED": "false",
    "FILES_ENABLED": "false",
    "NOTIFICATIONS_ENABLED": "false",
    "BACKGROUND_TASKS_ENABLED": "false",
}


def tables_of(modules: list[str]) -> list[str]:
    result = subprocess.run(
        [sys.executable, "-c", TABLES_SCRIPT, *modules],
        cwd=ROOT,
        env=os.environ | MINIMAL,
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(result.stdout.strip().splitlines()[-1])


def head_revision() -> str:
    revisions = []
    for path in (ROOT / "migrations" / "versions").glob("*.py"):
        if match := re.search(r'^revision: str = "(\w+)"', path.read_text(), re.M):
            revisions.append(match[1])
    downs = set()
    for path in (ROOT / "migrations" / "versions").glob("*.py"):
        downs |= set(re.findall(r'^down_revision: str \| None = "(\w+)"', path.read_text(), re.M))
    heads = [r for r in revisions if r not in downs]
    if len(heads) != 1:
        raise SystemExit(f"migrations: expected one head, found {heads}")
    return heads[0]


def migration(head: str, names: set[str], tables: list[str]) -> tuple[str, str]:
    number = f"{int(head) + 1:04d}" if head.isdigit() else datetime.now().strftime("%Y%m%d%H%M")
    label = "_".join(sorted(names))
    drops = "\n".join(f'    op.drop_table("{table}")' for table in tables)
    text = f'''"""strip: drop the tables of the removed modules ({", ".join(sorted(names))})

Revision ID: {number}
Revises: {head}
Create Date: {datetime.now():%Y-%m-%d %H:%M:%S}

Written by `make strip`.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "{number}"
down_revision: str | None = "{head}"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
{drops}


def downgrade() -> None:
    raise RuntimeError("The modules were removed with make strip: restore a backup instead")
'''
    return f"{number}_strip_{label}.py", text


def plan(names: set[str]) -> dict:
    specs = registry()
    known = {s["name"] for s in specs}
    if unknown := names - known:
        raise SystemExit(f"Unknown modules: {', '.join(sorted(unknown))} (known: {sorted(known)})")
    removed = with_dependents(names, specs)
    kept = [s["name"] for s in specs if s["name"] not in removed]
    paths = {s["name"]: s["path"] for s in specs}
    all_tables = tables_of([s["name"] for s in specs])
    kept_tables = set(tables_of(kept))
    marked = [
        str(path.relative_to(ROOT))
        for path in sorted(ROOT.rglob("*"))
        if path.is_file()
        and ".git" not in path.parts
        and "venv" not in path.parts
        and path.suffix in {".yml", ".yaml"}
        and MARKER.search(path.read_text())
    ]
    return {
        "removed": sorted(removed),
        "packages": [str(package_dir(paths[n]).relative_to(ROOT)) for n in sorted(removed)],
        "requirements": [f"requirements/{REQUIREMENTS[n]}" for n in sorted(removed) if n in REQUIREMENTS],
        "files": [f for n in sorted(removed) for f in EXTRA_FILES.get(n, []) if (ROOT / f).exists()],
        "tests": [str(p.relative_to(ROOT)) for p in marked_tests(removed)],
        "marked": marked,
        # Dropped children first
        "tables": [t for t in reversed(all_tables) if t not in kept_tables],
    }


def apply(steps: dict) -> None:
    removed = set(steps["removed"])
    for folder in steps["packages"]:
        shutil.rmtree(ROOT / folder)
    for name in steps["files"] + steps["tests"]:
        (ROOT / name).unlink()
    for name in steps["requirements"]:
        (ROOT / name).unlink()
        for other in (ROOT / "requirements").glob("*.txt"):
            other.write_text(without_requirement(other.read_text(), Path(name).name))
    modules = ROOT / "app" / "core" / "modules.py"
    modules.write_text(remove_registry_entries(modules.read_text(), removed))
    for name in steps["marked"]:
        path = ROOT / name
        path.write_text(remove_marked_blocks(path.read_text(), removed))
    if steps["tables"]:
        filename, text = migration(head_revision(), removed, steps["tables"])
        (ROOT / "migrations" / "versions" / filename).write_text(text)
        print(f"Wrote migrations/versions/{filename}")
    subprocess.run([sys.executable, "-m", "scripts.openapi"], cwd=ROOT, check=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Remove the modules a project does not use.")
    parser.add_argument("modules", nargs="*", help="Modules to remove (default: flags off in .env)")
    parser.add_argument("--apply", action="store_true", help="Remove them (default: only show)")
    parser.add_argument("--yes", action="store_true", help="Do not ask before removing")
    args = parser.parse_args(argv)

    steps = plan(set(args.modules) or disabled_by_settings())
    if not steps["removed"]:
        print("Nothing to remove: every module is on.")
        return 0
    print("Modules to remove:", ", ".join(steps["removed"]))
    for key in ("packages", "files", "requirements", "tests"):
        for item in steps[key]:
            print(f"  delete {item}")
    print("  edit   app/core/modules.py (the registry), openapi.json")
    for item in steps["marked"]:
        print(f"  edit   {item} (strip:begin blocks of these modules)")
    if steps["tables"]:
        print(f"  a migration drops the tables, with their data: {', '.join(steps['tables'])}")
    print("Kept: app/config.py and .env.example settings, the docs (edit them by hand).")
    if not args.apply:
        print("\nNothing changed. Run with --apply to remove.")
        return 0

    status = subprocess.run(
        ["git", "status", "--porcelain"], cwd=ROOT, capture_output=True, text=True, check=True
    )
    if status.stdout.strip():
        print("\nThe git working tree has changes: commit them first, so this can be undone.")
        return 1
    if not args.yes and input("\nType yes to remove: ").strip() != "yes":
        print("Cancelled.")
        return 1
    apply(steps)
    print("\nDone. Check with make lint and make test, then commit (git diff shows everything).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
