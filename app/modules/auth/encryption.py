"""Encryption of stored secrets: tokens of channels, secret settings, OAuth tokens.

Values are encrypted with Fernet (AES-128-CBC + HMAC-SHA256) under a key derived
from SECRET_KEY and stored as ``enc:<token>``. A value without the prefix is read as
it is (stored before encryption existed) and is encrypted with the next save, or by
migration 0013 and ``manage.py rotate-secrets``.

A new SECRET_KEY: move the old one to OLD_SECRET_KEYS (comma-separated), restart, run
``python manage.py rotate-secrets``, then remove it. A value no key can open (the key
is lost) is logged and read as empty: the channel is skipped, the app keeps working.

``encrypt`` / ``decrypt`` for single values, ``encrypt_fields`` / ``decrypt_fields`` for
the secret fields of a dict (entity parameters, settings), ``EncryptedText`` as a
column type.
"""

import base64
import logging
from collections.abc import Iterable
from functools import cache
from typing import Any

from cryptography.fernet import Fernet, InvalidToken, MultiFernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from sqlalchemy.types import Text, TypeDecorator

from app.config import config

logger = logging.getLogger(__name__)

PREFIX = "enc:"
# Ties the derived key to this use: SECRET_KEY also signs sessions and links
_PURPOSE = b"osnova: stored secrets"


def _fernet(secret: str) -> Fernet:
    key = HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=_PURPOSE).derive(
        secret.encode()
    )
    return Fernet(base64.urlsafe_b64encode(key))


@cache
def _cipher(current: str | None, old: str) -> MultiFernet:
    if not current:
        raise RuntimeError("Encrypted secrets need SECRET_KEY")
    keys = [current, *(key.strip() for key in old.split(",") if key.strip())]
    # Encrypts with the first key, opens with any of them
    return MultiFernet([_fernet(key) for key in keys])


def cipher() -> MultiFernet:
    return _cipher(config.SECRET_KEY, config.OLD_SECRET_KEYS)


def is_encrypted(value: Any) -> bool:
    return isinstance(value, str) and value.startswith(PREFIX)


def encrypt(value: str) -> str:
    """An empty value stays empty (nothing is set); an encrypted one stays as it is."""
    if not value or is_encrypted(value):
        return value
    return PREFIX + cipher().encrypt(value.encode()).decode()


def decrypt(value: str) -> str:
    """The plain value; one stored before encryption comes back unchanged."""
    if not is_encrypted(value):
        return value
    try:
        return cipher().decrypt(value[len(PREFIX) :].encode()).decode()
    except InvalidToken:
        logger.error("A stored secret cannot be decrypted: was SECRET_KEY changed?")
        return ""


def rotate(value: str) -> str:
    """Encrypted with the current key (a plain value gets encrypted)."""
    if not is_encrypted(value):
        return encrypt(value)
    try:
        return PREFIX + cipher().rotate(value[len(PREFIX) :].encode()).decode()
    except InvalidToken:
        logger.error("A stored secret cannot be decrypted: kept as it is")
        return value


def encrypt_fields(data: dict[str, Any], names: Iterable[str]) -> dict[str, Any]:
    secret = set(names)
    return {
        key: encrypt(value) if key in secret and isinstance(value, str) else value
        for key, value in data.items()
    }


def decrypt_fields(data: dict[str, Any], names: Iterable[str]) -> dict[str, Any]:
    secret = set(names)
    return {
        key: decrypt(value) if key in secret and isinstance(value, str) else value
        for key, value in data.items()
    }


class EncryptedText(TypeDecorator[str]):
    """A text column stored encrypted; the code reads and writes plain values."""

    impl = Text
    cache_ok = True

    def process_bind_param(self, value: str | None, dialect) -> str | None:
        return None if value is None else encrypt(value)

    def process_result_value(self, value: str | None, dialect) -> str | None:
        return None if value is None else decrypt(value)
