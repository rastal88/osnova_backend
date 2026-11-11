"""Base of a settings group and field types for settings."""

import re
from typing import Annotated, Any, ClassVar

from pydantic import AfterValidator, BaseModel, ConfigDict, Field
from pydantic_core import PydanticCustomError

from app.core.patterns import EMAIL_PATTERN, PHONE_PATTERN


def _optional_pattern(pattern: str, code: str):
    compiled = re.compile(pattern)

    def check(value: str) -> str:
        value = value.strip()
        if value and not compiled.match(value):
            raise PydanticCustomError(code, "Invalid value")
        return value

    return AfterValidator(check)


Email = Annotated[
    str,
    Field(min_length=3, max_length=254, json_schema_extra={"input": "email"}),
    _optional_pattern(EMAIL_PATTERN, "email_invalid"),
]
OptionalEmail = Annotated[
    str,
    Field(max_length=254, json_schema_extra={"input": "email"}),
    _optional_pattern(EMAIL_PATTERN, "email_invalid"),
]
OptionalPhone = Annotated[
    str,
    Field(max_length=20, json_schema_extra={"input": "tel"}),
    _optional_pattern(PHONE_PATTERN, "phone_invalid"),
]


# A password or token: rendered as a password input; APIs never send it back in clear
Secret = Annotated[
    str, Field(max_length=500, json_schema_extra={"input": "password", "secret": True})
]


def secret_fields(model: type[BaseModel]) -> set[str]:
    return {
        name
        for name, info in model.model_fields.items()
        if isinstance(info.json_schema_extra, dict) and info.json_schema_extra.get("secret")
    }


# Sent instead of a stored secret; sent back unchanged, it keeps the stored value
SECRET_MASK = "********"


def mask_secrets(model: type[BaseModel], values: dict[str, Any]) -> dict[str, Any]:
    """Values for an API answer: a set secret is replaced by SECRET_MASK."""
    secret = secret_fields(model)
    return {key: SECRET_MASK if key in secret and value else value for key, value in values.items()}


def keep_masked(
    model: type[BaseModel], data: dict[str, Any], stored: dict[str, Any]
) -> dict[str, Any]:
    """Incoming values: a secret sent back as SECRET_MASK keeps the stored (plain) one."""
    result = dict(data)
    for key in secret_fields(model):
        if result.get(key) == SECRET_MASK:
            result[key] = stored.get(key, "")
    return result


class SettingsGroup(BaseModel):
    """One group of settings, stored as one record. Every field needs a default."""

    # Stored values of removed fields are ignored, missing ones take defaults
    model_config = ConfigDict(extra="ignore", frozen=True)

    group: ClassVar[str]

    @classmethod
    def option_labels(cls, field: str) -> dict[str, str] | None:
        """Labels of select options that are not in the translations (e.g. language names)."""
        return None
