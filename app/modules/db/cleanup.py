"""Periodic cleanup of old rows.

A module that collects data to clean has a ``cleanup.py`` with
``async def cleanup(session) -> int`` (returns how many rows it removed) and an
entry in JOBS. ``run_cleanup`` runs the jobs of the enabled modules: every night
from Celery beat (the `maintenance.cleanup` task, app/modules/tasks) or from cron
with ``python manage.py cleanup`` in projects without Celery.
"""

import logging
from importlib import import_module

from app.config import config
from app.core.modules import resolve_enabled
from app.modules.db.database import standalone_session

logger = logging.getLogger(__name__)

# Module name (app/core/modules.py) -> where its job lives
JOBS: dict[str, str] = {
    "notifications": "app.modules.notifications.cleanup",
    "auth": "app.modules.auth.cleanup",
}


async def run_cleanup() -> dict[str, int]:
    """Run every job; one that fails is logged and does not stop the others."""
    enabled = {spec.name for spec in resolve_enabled(config)}
    removed: dict[str, int] = {}
    async with standalone_session() as session:
        for name, path in JOBS.items():
            if name not in enabled:
                continue
            try:
                removed[name] = await import_module(path).cleanup(session)
                await session.commit()
            except Exception:
                await session.rollback()
                logger.exception("Cleanup of %s failed", name)
    logger.info("Cleanup removed: %s", removed)
    return removed
