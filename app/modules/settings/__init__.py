"""Settings module: settings groups (app/settings.py) stored in the database and
edited in the admin.

Enabled together with the admin module. Values live in the `settings` table, one
JSON row per group, and are kept in process memory (app.core.settings). Every
process reloads them after SETTINGS_REFRESH_SECONDS, so several replicas pick up
a change without a shared cache.
"""

from fastapi import FastAPI


def register(app: FastAPI):
    from .refresh import SettingsRefreshMiddleware
    from .routes import settings_router

    app.include_router(settings_router, prefix="/api/v1/admin/settings", tags=["Admin"])
    app.add_middleware(SettingsRefreshMiddleware)
    return None
