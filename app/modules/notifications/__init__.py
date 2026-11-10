"""Notifications module: in-app notifications for signed-in users (the bell).

Enabled by NOTIFICATIONS_ENABLED. Requires the auth module. Send one from any
code with ``notify(session, users, kind, params, link)`` (service.py); texts
come from the "notifications" section of the locales and are translated when
read, so every user sees them in their own language. NOTIFICATIONS_CHANNELS
picks where else they go (channels.py: "email"; add Telegram the same way).
"""

from fastapi import FastAPI


def register(app: FastAPI):
    from app.modules.auth.hooks import on_user_delete

    from .routes import notifications_router
    from .service import delete_user_notifications

    on_user_delete(delete_user_notifications)

    app.include_router(notifications_router, prefix="/api/v1/notifications", tags=["Notifications"])
    return None
