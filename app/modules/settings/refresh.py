import asyncio
import logging
import time

from starlette.types import ASGIApp, Receive, Scope, Send

from app.config import config
from app.modules.db import app_session
from app.modules.settings.service import load_settings

logger = logging.getLogger(__name__)


class SettingsRefreshMiddleware:
    """Loads the settings before the first request and again when they are older
    than SETTINGS_REFRESH_SECONDS (one query per process per interval)."""

    def __init__(self, app: ASGIApp):
        self.app = app
        self.loaded_at: float | None = None
        self.lock = asyncio.Lock()

    def _stale(self) -> bool:
        return self.loaded_at is None or (
            time.monotonic() - self.loaded_at >= config.SETTINGS_REFRESH_SECONDS
        )

    async def refresh(self, scope: Scope) -> None:
        async with self.lock:
            if not self._stale():
                return
            try:
                async with app_session(scope["app"]) as session:
                    await load_settings(session)
            except Exception:
                logger.warning("Could not load settings, keeping current values", exc_info=True)
            # A failed load is retried after the same interval, not on every request
            self.loaded_at = time.monotonic()

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] == "http" and self._stale():
            await self.refresh(scope)
        await self.app(scope, receive, send)
