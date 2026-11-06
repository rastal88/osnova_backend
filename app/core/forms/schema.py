"""Form description: one source for server validation and the frontend.

A Form is a list of FormField. From it we build a Pydantic model (server
validation) and a JSON description (GET /forms/{name}) that the frontend
renders and uses for client-side rules.

Texts are translated from the "forms" section of app/core/locales/*.json:
"<form>.title", "<form>.submit", "<form>.success", "<form>.<field>" and,
for select options, "<form>.<field>.<option>".

Every form also gets a honeypot: a field named HONEYPOT_FIELD that the frontend
renders hidden. People leave it empty; a bot that fills it is dropped.
"""

import re
from dataclasses import dataclass, field
from functools import cache
from typing import Annotated, Any, Literal

from pydantic import AfterValidator, BaseModel, BeforeValidator, StringConstraints, create_model
from pydantic_core import PydanticCustomError

from app.core.i18n import translate

FieldType = Literal["text", "textarea", "email", "tel", "select", "checkbox", "consent"]

# Simple on purpose: both run in Python and in the browser (sent as `pattern`)
EMAIL_PATTERN = r"^[^\s@]+@[^\s@]+\.[^\s@]+$"
PHONE_PATTERN = r"^\+?[0-9 ()\-]{5,20}$"

# A name bots like to fill; forms cannot use it for a real field
HONEYPOT_FIELD = "website"

DEFAULT_MAX_LENGTH: dict[str, int] = {"text": 200, "textarea": 5000, "email": 254, "tel": 20}
TYPE_PATTERNS: dict[str, tuple[str, str]] = {
    "email": (EMAIL_PATTERN, "email_invalid"),
    "tel": (PHONE_PATTERN, "phone_invalid"),
}


@dataclass(frozen=True)
class FormField:
    name: str
    type: FieldType = "text"
    required: bool = False
    min_length: int | None = None
    max_length: int | None = None
    pattern: str | None = None
    options: tuple[str, ...] = ()

    def __post_init__(self):
        if self.type == "select" and not self.options:
            raise ValueError(f"Select field '{self.name}' needs options")


@dataclass(frozen=True)
class Form:
    name: str
    fields: tuple[FormField, ...] = field(default_factory=tuple)

    def __post_init__(self):
        if any(item.name == HONEYPOT_FIELD for item in self.fields):
            raise ValueError(f"Form '{self.name}' cannot have a field named '{HONEYPOT_FIELD}'")


def _blank(required: bool):
    """Empty strings count as missing: an error if required, None otherwise."""

    def check(value: Any) -> Any:
        if value is None or (isinstance(value, str) and not value.strip()):
            if required:
                raise PydanticCustomError("missing", "Field required")
            return None
        return value

    return BeforeValidator(check)


def _matches(pattern: str, code: str):
    compiled = re.compile(pattern)

    def check(value: str) -> str:
        if not compiled.match(value):
            raise PydanticCustomError(code, "Invalid value")
        return value

    return AfterValidator(check)


def _must_be_checked(value: bool) -> bool:
    if not value:
        raise PydanticCustomError("must_be_checked", "Must be checked")
    return value


def _max_length(item: FormField) -> int | None:
    return item.max_length or DEFAULT_MAX_LENGTH.get(item.type)


def _field_definition(item: FormField) -> tuple[Any, Any]:
    if item.type in ("checkbox", "consent"):
        if item.required or item.type == "consent":
            return Annotated[bool, AfterValidator(_must_be_checked)], ...
        return bool, False

    if item.type == "select":
        value_type: Any = Literal[item.options]  # type: ignore[valid-type]
        validators: list[Any] = []
    else:
        value_type = str
        validators = [
            StringConstraints(
                strip_whitespace=True,
                min_length=item.min_length,
                max_length=_max_length(item),
            )
        ]
        if item.type in TYPE_PATTERNS:
            validators.append(_matches(*TYPE_PATTERNS[item.type]))
        if item.pattern:
            validators.append(_matches(item.pattern, "string_pattern_mismatch"))

    if validators:
        value_type = Annotated[value_type, *validators]
    if item.required:
        return Annotated[value_type, _blank(True)], ...
    return Annotated[value_type | None, _blank(False)], None


class FormFieldOption(BaseModel):
    value: str
    label: str


class FormFieldDescription(BaseModel):
    name: str
    type: FieldType
    label: str
    required: bool
    min_length: int | None
    max_length: int | None
    pattern: str | None
    options: list[FormFieldOption]


class FormDescription(BaseModel):
    name: str
    title: str
    submit: str
    # Name of the hidden anti-spam field the frontend renders
    honeypot: str
    fields: list[FormFieldDescription]


class FormSubmitResponse(BaseModel):
    message: str


@cache
def build_model(form: Form) -> type[BaseModel]:
    fields = {item.name: _field_definition(item) for item in form.fields}
    return create_model(f"{form.name.title()}Form", **fields)


def describe(form: Form) -> FormDescription:
    """The form as the frontend sees it, in the request language."""

    def text(key: str) -> str:
        return translate(f"forms.{form.name}.{key}")

    return FormDescription.model_validate(
        {
            "name": form.name,
            "title": text("title"),
            "submit": text("submit"),
            "honeypot": HONEYPOT_FIELD,
            "fields": [
                {
                    "name": item.name,
                    "type": item.type,
                    "label": text(item.name),
                    "required": item.required or item.type == "consent",
                    "min_length": item.min_length,
                    "max_length": _max_length(item),
                    "pattern": item.pattern or TYPE_PATTERNS.get(item.type, (None,))[0],
                    "options": [
                        {"value": option, "label": text(f"{item.name}.{option}")}
                        for option in item.options
                    ],
                }
                for item in form.fields
            ],
        }
    )
