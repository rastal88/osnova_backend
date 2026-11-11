import logging
from collections.abc import Callable
from typing import Any

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import SettingsGroup, settings
from app.modules.settings.models import SettingsRecord
from app.settings import GROUPS

logger = logging.getLogger(__name__)

groups_by_name: dict[str, type[SettingsGroup]] = {group.group: group for group in GROUPS}


async def load_settings(session: AsyncSession) -> None:
    """Read every stored group into memory; groups without a record keep their defaults."""
    records = (await session.scalars(select(SettingsRecord))).all()
    stored = {record.group: record.values for record in records}
    for name, group in groups_by_name.items():
        if name not in stored:
            settings.set(group())
            continue
        try:
            settings.set(group.model_validate(stored[name]))
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
    """Validate (missing fields keep their current values), store and apply.
    ``before_commit(old, new)`` runs in the same transaction (e.g. the audit log)."""
    old = settings.get(group)
    value = group.model_validate({**old.model_dump(), **data})
    record = await session.get(SettingsRecord, group.group)
    if record is None:
        session.add(SettingsRecord(group=group.group, values=value.model_dump(mode="json")))
    else:
        record.values = value.model_dump(mode="json")
    if before_commit is not None:
        before_commit(old, value)
    await session.commit()
    settings.set(value)
    return value
