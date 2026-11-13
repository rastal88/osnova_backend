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
HEAVY = ["fastapi_users", "sqlalchemy", "celery", "redis", "asyncpg", "cryptography", "sentry_sdk"]

MINIMAL_SCRIPT = f"""
import json, sys
from fastapi.testclient import TestClient
from app import app
with TestClient(app) as client:
    status = client.get("/api/v1/health").status_code
    ready = client.get("/api/v1/ready").json()
    docs = [client.get(path).status_code for path in ("/docs", "/redoc", "/openapi.json")]
    api_docs = client.get("/api/v1/bootstrap").json()["api_docs"]
paths = sorted(app.openapi()["paths"])
loaded = [m for m in {HEAVY!r} if m in sys.modules]
result = {{"status": status, "ready": ready, "paths": paths, "loaded": loaded}}
result.update(docs=docs, api_docs=api_docs)
print(json.dumps(result))
"""


def test_minimal_profile_loads_no_optional_modules():
    # Explicit values also override a developer's local .env file.
    env = {
        **os.environ,
        **{flag: "false" for flag in FLAGS},
        "DATABASE_URL": "",
        "APP_PROFILE": "minimal",
        "DEBUG": "false",
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
    # Nothing to depend on in minimal
    assert data["ready"] == {"status": "ok", "checks": {}}
    assert data["loaded"] == []
    # Without DEBUG the API is not mapped publicly
    assert data["docs"] == [404, 404, 404]
    assert data["api_docs"] is False
    assert "APP_PROFILE" not in result.stdout
    assert not any(path.startswith("/api/v1/auth") for path in data["paths"])


def _settings(**overrides) -> Settings:
    values = {flag: False for flag in FLAGS} | {"DATABASE_URL": None} | overrides
    return Settings(_env_file=None, **values)


@pytest.mark.modules("auth")
def test_auth_requires_database():
    with pytest.raises(ModuleConfigError, match="db"):
        resolve_enabled(_settings(AUTH_ENABLED=True))


@pytest.mark.modules("admin")
def test_admin_requires_auth():
    with pytest.raises(ModuleConfigError, match="auth"):
        resolve_enabled(_settings(DATABASE_URL="sqlite+aiosqlite://", ADMIN_ENABLED=True))


def test_minimal_enables_nothing():
    assert resolve_enabled(_settings()) == []
