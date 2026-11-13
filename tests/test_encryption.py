"""Stored secrets are encrypted: values, key rotation, settings, OAuth tokens."""

import logging

import pytest
from sqlalchemy import select, text

from app.config import config
from app.core.settings import Secret, SettingsGroup, settings
from app.core.settings.schema import describe_group
from app.modules.auth.encryption import decrypt, encrypt, is_encrypted, rotate
from app.modules.auth.models import OAuthAccount, User
from manage import rotate_secrets
from tests.conftest import create_user

pytestmark = pytest.mark.modules("auth")

OTHER_KEY = "another-secret-key-for-tests-0123456789abcdef"


class MailSettings(SettingsGroup):
    group = "test_mail"

    host: str = "smtp.example.com"
    password: Secret = ""


@pytest.fixture
def mail_group(monkeypatch):
    from app.modules.settings import service as settings_service

    monkeypatch.setitem(settings_service.groups_by_name, MailSettings.group, MailSettings)
    return MailSettings


def test_values_are_encrypted_and_read_back():
    stored = encrypt("123:abc")
    assert is_encrypted(stored) and "123:abc" not in stored
    # A new token every time, the same value inside
    assert encrypt("123:abc") != stored
    assert decrypt(stored) == "123:abc"
    # Already encrypted and empty values stay as they are
    assert encrypt(stored) == stored
    assert encrypt("") == ""


def test_plain_values_from_before_are_read_as_they_are():
    assert decrypt("123:abc") == "123:abc"
    assert is_encrypted(rotate("123:abc"))


def test_old_keys_open_values_until_rotated(monkeypatch):
    stored = encrypt("123:abc")
    monkeypatch.setattr(config, "OLD_SECRET_KEYS", config.SECRET_KEY)
    monkeypatch.setattr(config, "SECRET_KEY", OTHER_KEY)
    assert decrypt(stored) == "123:abc"

    rotated = rotate(stored)
    monkeypatch.setattr(config, "OLD_SECRET_KEYS", "")
    assert decrypt(rotated) == "123:abc"


def test_a_lost_key_reads_as_empty(monkeypatch, caplog):
    stored = encrypt("123:abc")
    monkeypatch.setattr(config, "SECRET_KEY", OTHER_KEY)
    with caplog.at_level(logging.ERROR):
        assert decrypt(stored) == ""
    assert "cannot be decrypted" in caplog.text
    # Rotation keeps what it cannot open
    assert rotate(stored) == stored


# Settings and channels are stored by the admin module
@pytest.mark.anyio
@pytest.mark.modules("admin")
async def test_secret_settings_are_stored_encrypted_and_masked(database, mail_group):
    from app.modules.settings import service as settings_service
    from app.modules.settings.models import SettingsRecord

    async with database() as session:
        await settings_service.save_settings(session, mail_group, {"password": "s3cret"})
        record = await session.get(SettingsRecord, mail_group.group)
        assert record.values["host"] == "smtp.example.com"
        assert is_encrypted(record.values["password"])

    # The admin form never gets the secret back
    described = describe_group(mail_group, settings.get(mail_group))
    assert described.values["password"] == "********"

    # The mask sent back keeps it
    async with database() as session:
        await settings_service.save_settings(
            session, mail_group, {"host": "mail.example.com", "password": "********"}
        )
    assert settings.get(mail_group).password == "s3cret"

    # Read back from the database
    settings.reset()
    async with database() as session:
        await settings_service.load_settings(session)
    assert settings.get(mail_group).password == "s3cret"
    assert settings.get(mail_group).host == "mail.example.com"


@pytest.mark.anyio
async def test_oauth_tokens_are_stored_encrypted(database):
    await create_user(database, "g@example.com", "user")
    async with database() as session:
        user = await session.scalar(select(User).where(User.email == "g@example.com"))
        session.add(
            OAuthAccount(
                user_id=user.id,
                oauth_name="google",
                access_token="plain-access",
                refresh_token=None,
                account_id="1",
                account_email="g@example.com",
            )
        )
        await session.commit()

    async with database() as session:
        raw = (await session.execute(text("SELECT access_token FROM oauth_accounts"))).scalar()
        assert is_encrypted(raw)
        account = await session.scalar(select(OAuthAccount))
        assert (account.access_token, account.refresh_token) == ("plain-access", None)


@pytest.mark.anyio
@pytest.mark.modules("admin")
async def test_rotate_secrets_moves_everything_to_the_current_key(
    database, mail_group, monkeypatch
):
    import app as application
    from app.modules.entities.models import Entity
    from app.modules.settings.models import SettingsRecord

    monkeypatch.setattr(application.app.state, "modules", ["entities", "settings"])
    async with database() as session:
        session.add(
            Entity(
                type="lead_telegram",
                name="Chat",
                params={"bot_token": encrypt("123:abc"), "chat_id": "-1"},
            )
        )
        # Stored before encryption existed
        session.add(SettingsRecord(group=mail_group.group, values={"password": "plain"}))
        await session.commit()

    monkeypatch.setattr(config, "OLD_SECRET_KEYS", config.SECRET_KEY)
    monkeypatch.setattr(config, "SECRET_KEY", OTHER_KEY)
    async with database() as session:
        assert await rotate_secrets(session) == {"oauth": 0, "entities": 1, "settings": 1}

    monkeypatch.setattr(config, "OLD_SECRET_KEYS", "")
    async with database() as session:
        entity = await session.scalar(select(Entity))
        record = await session.get(SettingsRecord, mail_group.group)
    assert decrypt(entity.params["bot_token"]) == "123:abc"
    assert entity.params["chat_id"] == "-1"
    assert decrypt(record.values["password"]) == "plain"


@pytest.mark.anyio
@pytest.mark.modules("admin")
async def test_saving_a_channel_unchanged_records_no_secret_change(auth_client):
    from tests.conftest import login

    client, session_factory = auth_client
    await create_user(session_factory, "root@example.com", "root")
    await login(client, "root@example.com")
    channel = {
        "type": "lead_telegram",
        "name": "Chat",
        "params": {"bot_token": "123:abc", "chat_id": "-1"},
    }
    created = (await client.post("/api/v1/admin/entities", json=channel)).json()
    await client.put(
        f"/api/v1/admin/entities/{created['id']}",
        json={"params": {"bot_token": "********", "chat_id": "-1"}},
    )

    from app.modules.admin.models import AuditRecord

    async with session_factory() as session:
        actions = list(await session.scalars(select(AuditRecord.action)))
    # The token was encrypted again, but it did not change
    assert actions == ["entities.create"]
