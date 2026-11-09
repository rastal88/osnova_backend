"""Leads module: form submissions stored in the database and handled in the admin.

Enabled together with the admin module. Every valid submission of a form from
app/forms.py becomes a Lead (table `leads`); the admin lists, marks and deletes
them at /api/v1/admin/leads.
"""

from fastapi import FastAPI


def register(app: FastAPI):
    from app.core.forms.delivery import add_receiver

    from .routes import leads_router
    from .service import store_lead

    add_receiver(store_lead)
    app.include_router(leads_router, prefix="/api/v1/admin/leads", tags=["Admin"])
    return None
