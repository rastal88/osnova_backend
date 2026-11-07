import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from app.config import Settings
from app.core.modules import ModuleConfigError, resolve_enabled

ROOT = Path(__file__).resolve().parent.parent
FLAGS = [
    "AUTH_ENABLED",
    "ADMIN_ENABLED",
    "FILES_ENABLED",
    "NOTIFICATIONS_ENABLED",
    "BACKGROUND_TASKS_ENABLED",
]
HEAVY = ["fastapi_users", "sqlalchemy", "celery", "redis", "asyncpg"]

MINIMAL_SCRIPT = f"""
import json, sys
from fastapi.testclient import TestClient
from app import app
with TestClient(app) as client:
    status = client.get("/api/v1/health").status_code
paths = sorted(app.openapi()["paths"])
loaded = [m for m in {HEAVY!r} if m in sys.modules]
print(json.dumps({{"status": status, "paths": paths, "loaded": loaded}}))
"""


def test_minimal_profile_loads_no_optional_modules():
    # Explicit values also override a developer's local .env file.
    env = {
        **os.environ,
        **{flag: "false" for flag in FLAGS},
        "DATABASE_URL": "",
        "APP_PROFILE": "minimal",
    }
    result = subprocess.run(
        [sys.executable, "-c", MINIMAL_SCRIPT],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    data = json.loads(result.stdout.strip().splitlines()[-1])

    assert data["status"] == 200
    assert data["loaded"] == []
    assert not any(path.startswith("/api/v1/auth") for path in data["paths"])


def _settings(**overrides) -> Settings:
    values = {flag: False for flag in FLAGS} | {"DATABASE_URL": None} | overrides
    return Settings(_env_file=None, **values)


def test_auth_requires_database():
    with pytest.raises(ModuleConfigError, match="db"):
        resolve_enabled(_settings(AUTH_ENABLED=True))


def test_admin_requires_auth():
    with pytest.raises(ModuleConfigError, match="auth"):
        resolve_enabled(_settings(DATABASE_URL="sqlite+aiosqlite://", ADMIN_ENABLED=True))


def test_minimal_enables_nothing():
    assert resolve_enabled(_settings()) == []
