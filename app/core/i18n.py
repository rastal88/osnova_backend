"""Translations of backend messages.

Catalogs live in app/core/locales/<code>.json as sections of flat strings:
{"errors": {"not_found": "Not found"}}, looked up as "errors.not_found".
Placeholders use str.format syntax: "Up to {max_mb} MB".

The request language comes from the Accept-Language header (LanguageMiddleware)
and is kept in a context variable, so translate() works anywhere in a request.
"""

import json
from contextvars import ContextVar
from pathlib import Path

from starlette.datastructures import Headers, MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.languages import AVAILABLE_LANGUAGES, get_languages

LOCALES_DIR = Path(__file__).parent / "locales"

catalogs: dict[str, dict[str, dict[str, str]]] = {
    code: json.loads((LOCALES_DIR / f"{code}.json").read_text(encoding="utf-8"))
    for code in AVAILABLE_LANGUAGES
}

# Set per request by LanguageMiddleware; outside a request the default language is used
current_language: ContextVar[str | None] = ContextVar("current_language", default=None)


def get_language() -> str:
    return current_language.get() or get_languages().default


def resolve_language(accept_language: str | None) -> str:
    """Pick the best enabled language from an Accept-Language header."""
    enabled = get_languages()
    candidates: list[tuple[float, int, str]] = []
    for index, part in enumerate((accept_language or "").split(",")):
        tag, _, params = part.strip().partition(";")
        quality = 1.0
        if params.strip().startswith("q="):
            try:
                quality = float(params.strip()[2:])
            except ValueError:
                continue
        code = tag.strip().lower().split("-")[0]
        if code in enabled.codes and quality > 0:
            candidates.append((-quality, index, code))
    return min(candidates)[2] if candidates else enabled.default


def has_translation(key: str) -> bool:
    section, _, name = key.partition(".")
    return name in catalogs[get_languages().default].get(section, {})


def translate(key: str, language: str | None = None, **params) -> str:
    """Translate a key; falls back to the default language, then to the key itself."""
    section, _, name = key.partition(".")
    for code in (language or get_language(), get_languages().default):
        message = catalogs.get(code, {}).get(section, {}).get(name)
        if message is not None:
            if not params:
                return message
            try:
                return message.format(**params)
            except (KeyError, IndexError):
                return message
    return key


class LanguageMiddleware:
    """Sets the request language and answers with Content-Language."""

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        language = resolve_language(Headers(scope=scope).get("accept-language"))
        token = current_language.set(language)

        async def send_with_language(message: Message):
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                headers["Content-Language"] = language
                headers.add_vary_header("Accept-Language")
            await send(message)

        try:
            await self.app(scope, receive, send_with_language)
        finally:
            current_language.reset(token)
