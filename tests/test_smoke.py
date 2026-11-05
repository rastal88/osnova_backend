import pytest
from httpx import AsyncClient, ASGITransport
import os

os.environ["BACKGROUND_TASKS_ENABLED"] = "false"
os.environ["APP_NAME"] = "TestApp"
os.environ["APP_VERSION"] = "1.0.0"
os.environ["APP_PROFILE"] = "minimal"
os.environ["APP_HOST"] = "localhost"
os.environ["APP_PORT"] = "8000"
os.environ["DEBUG"] = "true"
os.environ["DATABASE_URL"] = "postgresql+asyncpg://user:pass@localhost/db"
os.environ["SECRET_KEY"] = "supersecretkey"
os.environ["ALGORITHM"] = "HS256"
os.environ["ACCESS_TOKEN_EXPIRE_MINUTES"] = "30"
os.environ["REDIS_URL"] = "redis://localhost:6379"
os.environ["CELERY_BROKER_URL"] = "redis://localhost:6379"
os.environ["CELERY_RESULT_BACKEND"] = "redis://localhost:6379"
os.environ["AUTH_ENABLED"] = "true"
os.environ["ADMIN_ENABLED"] = "true"
os.environ["FILES_ENABLED"] = "true"
os.environ["NOTIFICATIONS_ENABLED"] = "true"
os.environ["OAUTH2_CLIENT_ID"] = ""
os.environ["OAUTH2_CLIENT_SECRET"] = ""
os.environ["OAUTH2_REDIRECT_URI"] = ""

from app import create_app

@pytest.fixture
def anyio_backend():
    return "asyncio"

@pytest.mark.anyio
async def test_health_endpoint():
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/api/v1/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

@pytest.mark.anyio
async def test_bootstrap_endpoint():
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/api/v1/bootstrap")
        assert response.status_code == 200
        data = response.json()
        assert "profile" in data
        assert data["profile"] == "minimal"

@pytest.mark.anyio
async def test_file_upload_download():
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        files = {"file": ("test.txt", b"hello world", "text/plain")}
        response = await ac.post("/api/v1/file_flow/upload", files=files)
        assert response.status_code == 200
        data = response.json()
        assert data["filename"] == "test.txt"
        
        download_res = await ac.get(data["url"])
        assert download_res.status_code == 200
        assert download_res.content == b"hello world"

@pytest.mark.anyio
async def test_admin_users_unauthorized():
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/api/v1/admin_flow/users")
        assert response.status_code == 401
