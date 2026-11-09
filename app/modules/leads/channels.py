"""Lead delivery channels: entity types (app/core/entities) of the group "lead_channels".

Each channel sends a LeadMessage with ``send`` (synchronous, standard library
only). A transient failure (network, server error) raises an ordinary
exception and the delivery is retried; DeliveryRejected means retrying will
not help (wrong token, a 4xx answer). To add a channel: a class here with
``@entity_type`` and its texts in the "entities" section of the locales.
"""

import hashlib
import hmac
import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Annotated, Any

from pydantic import AfterValidator, Field
from pydantic_core import PydanticCustomError

from app.core.entities import EntityType, entity_type
from app.core.mail import EmailMessage, deliver
from app.core.settings import Email, Secret

GROUP = "lead_channels"
TIMEOUT = 10
TELEGRAM_LIMIT = 4096


class DeliveryRejected(Exception):
    """The receiver refused the message: retrying will not help."""


@dataclass(frozen=True)
class LeadMessage:
    id: str
    form: str
    title: str
    language: str
    created_at: str
    # (label, value as text) in the form order
    fields: list[tuple[str, str]]
    data: dict[str, Any]

    @property
    def text(self) -> str:
        lines = [f"{label}: {value}" for label, value in self.fields]
        return "\n".join([self.title, "", *lines])


def _json(payload: dict) -> bytes:
    return json.dumps(payload, ensure_ascii=False).encode()


def _post_json(url: str, body: bytes, headers: dict[str, str] | None = None) -> None:
    request = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={"Content-Type": "application/json", "User-Agent": "Osnova", **(headers or {})},
    )
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT):
            pass
    except urllib.error.HTTPError as exc:
        detail = exc.read(500).decode(errors="replace")
        if exc.code < 500 and exc.code != 429:
            raise DeliveryRejected(f"HTTP {exc.code}: {detail}") from exc
        raise


def _http_url(value: str) -> str:
    if not value.startswith(("https://", "http://")):
        raise PydanticCustomError("url_invalid", "The address must start with https://")
    return value


@entity_type
class EmailChannel(EntityType):
    type = "lead_email"
    group = GROUP

    to: Email

    def send(self, message: LeadMessage) -> None:
        deliver(EmailMessage(to=self.to, subject=message.title, text=message.text))


@entity_type
class TelegramChannel(EntityType):
    type = "lead_telegram"
    group = GROUP

    bot_token: Annotated[Secret, Field(min_length=1)]
    chat_id: str = Field(min_length=1, max_length=64)

    def send(self, message: LeadMessage) -> None:
        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        _post_json(url, _json({"chat_id": self.chat_id, "text": message.text[:TELEGRAM_LIMIT]}))


@entity_type
class WebhookChannel(EntityType):
    type = "lead_webhook"
    group = GROUP

    url: Annotated[str, Field(min_length=1, max_length=500), AfterValidator(_http_url)]
    # Optional: signs the body, header X-Osnova-Signature: sha256=<hex HMAC>
    secret: Secret = ""

    def send(self, message: LeadMessage) -> None:
        payload = {
            "id": message.id,
            "form": message.form,
            "language": message.language,
            "created_at": message.created_at,
            "data": message.data,
        }
        body = _json(payload)
        headers = {}
        if self.secret:
            digest = hmac.new(self.secret.encode(), body, hashlib.sha256).hexdigest()
            headers["X-Osnova-Signature"] = f"sha256={digest}"
        _post_json(self.url, body, headers)
