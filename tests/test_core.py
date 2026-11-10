import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.anyio
async def test_health(client):
    response = await client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.anyio
async def test_bootstrap(client):
    response = await client.get("/api/v1/bootstrap")
    assert response.status_code == 200
    data = response.json()
    assert data["profile"] == "standard"
    assert data["features"]["authentication"] is True
    assert data["i18n"] == {
        "languages": [
            {"code": "en", "name": "English"},
            {"code": "ru", "name": "Русский"},
        ],
        "default": "en",
    }


def test_openapi_json_is_up_to_date():
    # Separate process: the export enables every module through the environment
    result = subprocess.run(
        [sys.executable, "-m", "scripts.openapi", "--check"],
        cwd=Path(__file__).resolve().parent.parent,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr


@pytest.mark.anyio
async def test_docs_are_served_in_debug(client):
    # The test session runs with DEBUG=true; without it see test_modules.py
    assert (await client.get("/docs")).status_code == 200
    assert (await client.get("/openapi.json")).status_code == 200
