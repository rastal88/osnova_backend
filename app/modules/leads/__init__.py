"""Leads module: form submissions stored in the database, delivered to channels
and handled in the admin.

Enabled together with the admin module. Every valid submission of a form from
app/forms.py becomes a Lead (table `leads`) and is sent to the enabled delivery
channels — entities of the group "lead_channels": email, Telegram, webhook
(channels.py, delivery.py). The admin lists, marks and deletes leads at
/api/v1/admin/leads and sets channels up at /api/v1/admin/entities.
"""

from fastapi import FastAPI


def register(app: FastAPI):
    from app.core.forms.delivery import add_receiver

    from . import channels  # noqa: F401  registers the channel types
    from .routes import leads_router
    from .service import store_lead

    add_receiver(store_lead)
    app.include_router(leads_router, prefix="/api/v1/admin/leads", tags=["Admin"])
    return None
