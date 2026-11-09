"""Base of a settings group and field types for settings."""

import re
from typing import Annotated, ClassVar

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


class SettingsGroup(BaseModel):
    """One group of settings, stored as one record. Every field needs a default."""

    # Stored values of removed fields are ignored, missing ones take defaults
    model_config = ConfigDict(extra="ignore", frozen=True)

    group: ClassVar[str]

    @classmethod
    def option_labels(cls, field: str) -> dict[str, str] | None:
        """Labels of select options that are not in the translations (e.g. language names)."""
        return None
