"""Writes .env for the quick start (`make init`): the standard profile in Docker with every
capability on, random secrets and migrations on start. Never overwrites an existing .env.

Only the standard library, so it runs before `make install`.
"""

from __future__ import annotations

import os
import re
import secrets
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Values for the quick start; everything else keeps the defaults of .env.example
QUICK_START = {
    "APP_PROFILE": "standard",
    "AUTH_ENABLED": "true",
    "ADMIN_ENABLED": "true",
    "FILES_ENABLED": "true",
    "NOTIFICATIONS_ENABLED": "true",
    "BACKGROUND_TASKS_ENABLED": "true",
    # One backend in standard: it applies the migrations on start (not with replicas)
    "RUN_MIGRATIONS": "true",
}


def render(example: str, values: dict[str, str]) -> str:
    """The example with `KEY=...` (or a commented `# KEY=...`) set to the given values;
    keys the example does not have are added at the end."""
    left = dict(values)

    def replace(match: re.Match) -> str:
        key = match.group(1)
        if key not in left:
            return match.group(0)
        return f"{key}={left.pop(key)}"

    text = re.sub(r"^(?:# ?)?([A-Z][A-Z0-9_]*)=.*$", replace, example, flags=re.M)
    if left:
        text = text.rstrip("\n") + "\n\n" + "".join(f"{k}={v}\n" for k, v in left.items())
    return text


def quick_start_values() -> dict[str, str]:
    return QUICK_START | {
        "SECRET_KEY": secrets.token_urlsafe(48),
        "POSTGRES_PASSWORD": secrets.token_urlsafe(24),
    }


def main() -> int:
    target = ROOT / ".env"
    if target.exists():
        print(".env already exists and is left as it is (delete or rename it to start over).")
        return 1
    example = (ROOT / ".env.example").read_text()
    # Readable by its owner only: it holds the secrets
    fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as out:
        out.write(render(example, quick_start_values()))
    print(
        "Wrote .env: standard profile, every capability on, random SECRET_KEY and "
        "POSTGRES_PASSWORD.\nNext: make up-standard, then make createroot; the site is at "
        "http://localhost:8080 (FRONTEND_PORT)."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
