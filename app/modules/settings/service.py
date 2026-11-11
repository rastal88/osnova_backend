import asyncio
import logging
import time
from collections.abc import Callable
from importlib import import_module
from importlib.util import find_spec
from typing import Any

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import config
from app.core.modules import resolve_enabled
from app.core.settings import SettingsGroup, keep_masked, secret_fields, settings
from app.modules.auth.encryption import decrypt_fields, encrypt_fields
from app.modules.auth.permissions import permission
from app.modules.settings.models import SettingsRecord
from app.settings import GROUPS

logger = logging.getLogger(__name__)


def _known_groups() -> dict[str, type[SettingsGroup]]:
    """The project's groups (app/settings.py) and those of the enabled modules: a
    module's ``settings.py`` with ``GROUPS`` (e.g. app/modules/files/settings.py)."""
    groups = list(GROUPS)
    for spec in resolve_enabled(config):
        path = f"{spec.path}.settings"
        if spec.path != __package__ and find_spec(path):
            groups.extend(import_module(path).GROUPS)
    return {group.group: group for group in groups}


groups_by_name: dict[str, type[SettingsGroup]] = _known_groups()


def group_permission(name: str) -> str:
    """Changing a group (and seeing one with secrets): ``settings.<group>``."""
    return f"settings.{name}"


for _name in groups_by_name:
    permission(group_permission(_name))


async def load_settings(session: AsyncSession) -> None:
    """Read every stored group into memory; groups without a record keep their defaults."""
    records = (await session.scalars(select(SettingsRecord))).all()
    stored = {record.group: record.values for record in records}
    for name, group in groups_by_name.items():
        if name not in stored:
            settings.set(group())
            continue
        try:
            settings.set(group.model_validate(decrypt_fields(stored[name], secret_fields(group))))
        except ValidationError:
            # E.g. a language removed from the code: fall back to the defaults
            logger.warning("Stored settings '%s' are invalid, using defaults", name)
            settings.set(group())


async def save_settings(
    session: AsyncSession,
    group: type[SettingsGroup],
    data: dict[str, Any],
    before_commit: Callable[[SettingsGroup, SettingsGroup], None] | None = None,
) -> SettingsGroup:
    """Validate (missing fields keep their current values, a masked secret keeps the
    stored one), store with secrets encrypted and apply. ``before_commit(old, new)`` runs
    in the same transaction (e.g. the audit log)."""
    old = settings.get(group)
    current = old.model_dump()
    value = group.model_validate({**current, **keep_masked(group, data, current)})
    values = encrypt_fields(value.model_dump(mode="json"), secret_fields(group))
    record = await session.get(SettingsRecord, group.group)
    if record is None:
        session.add(SettingsRecord(group=group.group, values=values))
    else:
        record.values = values
    if before_commit is not None:
        before_commit(old, value)
    await session.commit()
    settings.set(value)
    return value


_loaded_at: float | None = None


def refresh_stored_settings() -> None:
    """Load the settings changed in the admin in a process without the web middleware
    (the Celery worker, before a task); again after SETTINGS_REFRESH_SECONDS."""
    global _loaded_at
    if _loaded_at is not None and time.monotonic() - _loaded_at < config.SETTINGS_REFRESH_SECONDS:
        return
    try:
        asyncio.get_running_loop()
        # Inside the web process (a task run eagerly): the middleware keeps them fresh
        return
    except RuntimeError:
        pass
    from app.modules.db.database import standalone_session

    async def load() -> None:
        async with standalone_session() as session:
            await load_settings(session)

    try:
        asyncio.run(load())
    except Exception:
        logger.warning("Could not load settings, keeping current values", exc_info=True)
    _loaded_at = time.monotonic()
