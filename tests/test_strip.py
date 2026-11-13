"""`make strip`: the pieces of scripts/strip.py (CI strips a copy of each module for real)."""

import pytest

from scripts import strip
from tests.conftest import PRESENT

SPECS = [
    {"name": "db", "path": "app.modules.db", "requires": []},
    {"name": "auth", "path": "app.modules.auth", "requires": ["db"]},
    {"name": "admin", "path": "app.modules.admin", "requires": ["auth"]},
    {"name": "leads", "path": "app.modules.leads", "requires": ["admin"]},
    {"name": "files", "path": "app.modules.files", "requires": ["auth"]},
    {"name": "tasks", "path": "app.modules.tasks", "requires": []},
]


def test_a_module_goes_with_the_modules_that_need_it():
    assert strip.with_dependents({"files"}, SPECS) == {"files"}
    assert strip.with_dependents({"admin"}, SPECS) == {"admin", "leads"}
    assert strip.with_dependents({"auth"}, SPECS) == {"auth", "admin", "leads", "files"}
    # The database stays
    assert strip.with_dependents({"db"}, SPECS) == set()


OPTIONAL = sorted(PRESENT - {"db", "user"})


@pytest.mark.skipif(not OPTIONAL, reason="every optional module was removed")
@pytest.mark.parametrize("name", OPTIONAL)
def test_registry_entry_is_removed(name):
    text = (strip.ROOT / "app" / "core" / "modules.py").read_text()
    stripped = strip.remove_registry_entries(text, {name})
    assert f'name="{name}"' not in stripped
    assert stripped.count("ModuleSpec(\n") == text.count("ModuleSpec(\n") - 1
    compile(stripped, "modules.py", "exec")


def test_unknown_registry_entry_stops():
    with pytest.raises(SystemExit):
        strip.remove_registry_entries("MODULES = ()\n", {"files"})


BLOCKS = """services:
  backend: {}
  # strip:begin tasks — worker and beat
  worker: {}
  beat: {}
  # strip:end
  # strip:begin auth files
  stack: {}
  # strip:end
  # strip:begin any
  strip: {}
  # strip:end
volumes: {}
"""


def test_marked_blocks_of_removed_modules_go():
    assert strip.remove_marked_blocks(BLOCKS, {"tasks"}) == (
        "services:\n  backend: {}\n  # strip:begin auth files\n  stack: {}\n  # strip:end\n"
        "volumes: {}\n"
    )
    assert strip.remove_marked_blocks(BLOCKS, {"files"}) == (
        "services:\n  backend: {}\n  # strip:begin tasks — worker and beat\n  worker: {}\n"
        "  beat: {}\n  # strip:end\nvolumes: {}\n"
    )


def test_unclosed_block_stops():
    with pytest.raises(SystemExit):
        strip.remove_marked_blocks("# strip:begin files\nx: 1\n", {"files"})


def test_requirement_lines_go():
    text = "# All\n-r db.txt\n-r files.txt\n-r tasks.txt\n"
    assert strip.without_requirement(text, "files.txt") == "# All\n-r db.txt\n-r tasks.txt\n"


def test_migration_drops_the_tables_and_cannot_be_undone():
    filename, text = strip.migration("0014", {"files", "notifications"}, ["files", "notes"])
    assert filename == "0015_strip_files_notifications.py"
    assert 'revision: str = "0015"' in text
    assert 'down_revision: str | None = "0014"' in text
    assert text.index('op.drop_table("files")') < text.index('op.drop_table("notes")')
    assert "raise RuntimeError" in text
    compile(text, filename, "exec")
    assert strip.migration("0014", set("abcd"), ["x"])[0] == "0015_strip_4_modules.py"


def test_head_revision_is_the_last_migration():
    assert strip.head_revision().isdigit()


@pytest.mark.skipif("files" not in PRESENT, reason="no files module")
def test_dry_run_changes_nothing(capsys):
    before = (strip.ROOT / "app" / "core" / "modules.py").read_text()
    assert strip.main(["files"]) == 0
    out = capsys.readouterr().out
    assert "Modules to remove: files" in out
    assert "delete app/modules/files" in out
    assert "drops the tables, with their data: files" in out
    assert "Nothing changed" in out
    assert (strip.ROOT / "app" / "core" / "modules.py").read_text() == before


def test_unknown_module_stops():
    with pytest.raises(SystemExit, match="Unknown modules: shop"):
        strip.main(["shop"])
