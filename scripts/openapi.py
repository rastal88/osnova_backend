"""Write the OpenAPI schema of the full API (every module enabled) to openapi.json.

The frontend generates its API types from this file (osnova_frontend: npm run
generate:client). Run after changing endpoints or their models:

    python -m scripts.openapi           # write openapi.json
    python -m scripts.openapi --check   # fail if openapi.json is out of date
"""

import json
import os
import runpy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "openapi.json"
# Read without importing the app package: importing it builds the app with the local .env
VERSION = runpy.run_path(str(ROOT / "app" / "version.py"))["VERSION"]

# Explicit values, so a developer's .env does not change the schema
ENV = {
    "APP_NAME": "Osnova Application",
    "APP_VERSION": VERSION,
    "APP_PROFILE": "standard",
    "AUTH_ENABLED": "true",
    "ADMIN_ENABLED": "true",
    "FILES_ENABLED": "true",
    "NOTIFICATIONS_ENABLED": "true",
    "BACKGROUND_TASKS_ENABLED": "true",
    "AUTH_STRATEGY": "jwt",
    # Only to load the modules: nothing connects while the schema is built
    "DATABASE_URL": "postgresql+asyncpg://osnova:osnova@localhost/osnova",
    "SECRET_KEY": "openapi-export-not-a-real-secret-key",
    # So the OAuth routes are in the schema
    "GOOGLE_CLIENT_ID": "openapi-export",
    "GOOGLE_CLIENT_SECRET": "openapi-export",
    "CELERY_BROKER_URL": "memory://",
}


def render() -> str:
    os.environ.update(ENV)
    from app import app

    return json.dumps(app.openapi(), indent=2, ensure_ascii=False) + "\n"


def main() -> int:
    schema = render()
    if "--check" in sys.argv:
        if not OUTPUT.exists() or OUTPUT.read_text(encoding="utf-8") != schema:
            print(
                "openapi.json is out of date: run `make openapi`"
                " (after `make install` if requirements changed)",
                file=sys.stderr,
            )
            return 1
        print("openapi.json is up to date")
        return 0
    OUTPUT.write_text(schema, encoding="utf-8")
    print(f"Wrote {OUTPUT.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
