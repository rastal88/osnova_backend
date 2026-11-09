from typing import TypeVar

from app.core.settings.base import SettingsGroup

G = TypeVar("G", bound=SettingsGroup)


class SettingsStore:
    """Current values of every settings group, kept in process memory."""

    def __init__(self) -> None:
        self._values: dict[str, SettingsGroup] = {}

    def get(self, group: type[G]) -> G:
        value = self._values.get(group.group)
        if not isinstance(value, group):
            value = group()
            self._values[group.group] = value
        return value

    def set(self, value: SettingsGroup) -> None:
        self._values[value.group] = value

    def reset(self) -> None:
        """Back to the defaults (tests)."""
        self._values.clear()


settings = SettingsStore()
