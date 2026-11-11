from typing import Any

from app.core.i18n import has_translation, translate


def render(kind: str, params: dict[str, Any], language: str | None = None) -> tuple[str, str]:
    """(title, body) in the language (the current one by default); an unknown kind shows
    its name."""
    title_key = f"notifications.{kind}.title"
    if not has_translation(title_key):
        return kind, ""
    body_key = f"notifications.{kind}.body"
    return translate(title_key, language, **params), translate(body_key, language, **params)
