"""Settings moved from .env to the admin: a permission per group, mail with a test
email, limits that change without a restart, module groups, the worker."""

import smtplib

import pytest
from sqlalchemy import insert

from app.core.mail import EmailMessage, sending
from app.core.mail.settings import MailSettings
from app.core.modules import MODULES
from app.core.settings import settings
from app.modules.auth.models import RoleRecord
from app.modules.settings import service
from tests.conftest import create_user, login

pytestmark = [pytest.mark.anyio, pytest.mark.modules("admin")]

SETTINGS = "/api/v1/admin/settings"
FORM = "/api/v1/forms/contact"
CONTACT = {
    "name": "Ann",
    "email": "ann@example.com",
    "message": "Please call me back tomorrow",
    "consent": True,
}


@pytest.fixture
def outbox(monkeypatch):
    sent: list[EmailMessage] = []
    monkeypatch.setitem(sending.BACKENDS, "console", sent.append)
    return sent


async def _with_role(auth_client, permissions: list[str]):
    """Signed in with a role that has only these permissions (and the admin area)."""
    client, session_factory = auth_client
    async with session_factory() as session:
        await session.execute(
            insert(RoleRecord),
            [{"slug": "ops", "name": "Ops", "permissions": ["admin.access", *permissions]}],
        )
        await session.commit()
    await create_user(session_factory, "ops@example.com", "ops")
    await login(client, "ops@example.com")
    return client


async def _root(auth_client):
    client, session_factory = auth_client
    await create_user(session_factory, "root@example.com", "root")
    await login(client, "root@example.com")
    return client


async def test_a_group_is_changed_with_its_own_permission(auth_client):
    client = await _with_role(auth_client, ["settings.site"])

    groups = {group["name"]: group for group in (await client.get(SETTINGS)).json()}
    assert groups["site"]["editable"] is True
    assert groups["languages"]["editable"] is False
    # Groups with secrets are not even shown
    assert "mail" not in groups and "protection" not in groups

    assert (await client.put(f"{SETTINGS}/site", json={"name": "New"})).status_code == 200
    response = await client.put(f"{SETTINGS}/languages", json={"default": "ru"})
    assert response.status_code == 403
    assert (await client.post(f"{SETTINGS}/mail/test")).status_code == 403


async def test_mail_password_is_never_sent_back(auth_client):
    client = await _root(auth_client)
    response = await client.put(
        f"{SETTINGS}/mail",
        json={"backend": "smtp", "smtp_host": "mail.example.com", "smtp_password": "p4ss"},
    )
    assert response.status_code == 200, response.text
    values = response.json()["values"]
    assert (values["smtp_host"], values["smtp_password"]) == ("mail.example.com", "********")
    assert settings.get(MailSettings).smtp_password == "p4ss"

    # Saved again with the mask: the password stays
    await client.put(f"{SETTINGS}/mail", json={**values, "smtp_port": 465})
    assert settings.get(MailSettings).smtp_password == "p4ss"
    assert settings.get(MailSettings).smtp_port == 465


async def test_test_email_goes_to_the_admin(auth_client, outbox, monkeypatch):
    client = await _root(auth_client)

    # In the admin's own language, like every email to a user
    response = await client.post(f"{SETTINGS}/mail/test", headers={"Accept-Language": "ru"})
    assert response.json() == {"ok": True, "error": None}
    (message,) = outbox
    assert message.to == "root@example.com"
    assert message.subject == "Test email from TestApp"

    def refused(message):
        raise smtplib.SMTPAuthenticationError(535, b"Bad credentials")

    monkeypatch.setitem(sending.BACKENDS, "smtp", refused)
    await client.put(f"{SETTINGS}/mail", json={"backend": "smtp"})
    result = (await client.post(f"{SETTINGS}/mail/test")).json()
    assert result["ok"] is False
    assert "Bad credentials" in result["error"]


async def test_rate_limit_changes_without_a_restart(auth_client):
    client = await _root(auth_client)
    response = await client.put(f"{SETTINGS}/protection", json={"forms_rate_limit": "1/hour"})
    assert response.status_code == 200, response.text

    assert (await client.post(FORM, json=CONTACT)).status_code == 200
    assert (await client.post(FORM, json=CONTACT)).status_code == 429

    await client.put(f"{SETTINGS}/protection", json={"forms_rate_limit": ""})
    assert (await client.post(FORM, json=CONTACT)).status_code == 200


async def test_a_wrong_rate_limit_is_a_field_error(auth_client):
    client = await _root(auth_client)
    response = await client.put(
        f"{SETTINGS}/protection",
        json={"auth_rate_limit": "lots"},
        headers={"Accept-Language": "ru"},
    )
    assert response.status_code == 422
    (field,) = response.json()["fields"]
    assert (field["field"], field["code"]) == ("auth_rate_limit", "rate_limit_invalid")


async def test_numbers_are_described_with_their_range(auth_client):
    client = await _root(auth_client)
    groups = {group["name"]: group for group in (await client.get(SETTINGS)).json()}
    port = next(field for field in groups["mail"]["fields"] if field["name"] == "smtp_port")
    assert (port["type"], port["min_value"], port["max_value"]) == ("number", 1, 65535)
    assert groups["retention"]["values"]["audit_days"] == 365


def test_groups_of_disabled_modules_are_not_known(monkeypatch):
    without = tuple(spec for spec in MODULES if spec.name not in ("files", "notifications"))
    monkeypatch.setattr("app.core.modules.MODULES", without)
    names = list(service._known_groups())
    assert names == ["site", "languages", "mail", "protection", "retention"]


async def test_worker_refresh_leaves_the_web_process_alone(monkeypatch):
    """Inside a running event loop (a task run eagerly) the middleware already keeps
    the settings fresh: nothing is loaded."""
    monkeypatch.setattr(service, "_loaded_at", None)
    service.refresh_stored_settings()
    assert service._loaded_at is None
