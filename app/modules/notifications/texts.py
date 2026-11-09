from typing import Any

from app.core.i18n import has_translation, translate


def render(kind: str, params: dict[str, Any]) -> tuple[str, str]:
    """(title, body) in the current language; an unknown kind shows its name."""
    title_key = f"notifications.{kind}.title"
    if not has_translation(title_key):
        return kind, ""
    return translate(title_key, **params), translate(f"notifications.{kind}.body", **params)
