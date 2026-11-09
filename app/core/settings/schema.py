"""Description of a settings group for the generated admin form.

The description has the same shape as a form description (app/core/forms), so
the frontend renders the edit form with the same SchemaForm. Field types:

- ``str`` → text (``Field(json_schema_extra={"input": "textarea"})`` for others;
  OptionalEmail / OptionalPhone set email / tel);
- ``bool`` → checkbox;
- ``Literal[...]`` → select; ``list[Literal[...]]`` → multiselect.

Texts come from the "settings" section of app/core/locales/*.json:
"<group>.title", "<group>.<field>" and, for options, "<group>.<field>.<option>"
(or the group's ``option_labels``).
"""

from typing import Any, Literal, get_args, get_origin

from annotated_types import MaxLen, MinLen
from pydantic import BaseModel
from pydantic.fields import FieldInfo

from app.core.forms.schema import FieldType, FormFieldDescription
from app.core.i18n import translate
from app.core.patterns import EMAIL_PATTERN, PHONE_PATTERN
from app.core.settings.base import SettingsGroup


class SettingsGroupDescription(BaseModel):
    name: str
    title: str
    fields: list[FormFieldDescription]
    values: dict[str, Any]


def _constraint(info: FieldInfo, kind: type) -> int | None:
    for item in info.metadata:
        if isinstance(item, kind):
            return item.min_length if isinstance(item, MinLen) else item.max_length
    return None


def describe_field(
    name: str,
    info: FieldInfo,
    key: str,
    option_labels: dict[str, str] | None = None,
) -> dict:
    """One model field as a form field; texts from "<key>.<name>" (and ".<option>")."""
    annotation = info.annotation
    options: tuple[str, ...] = ()
    field_type: FieldType
    if annotation is bool:
        field_type = "checkbox"
    elif get_origin(annotation) is Literal:
        field_type, options = "select", get_args(annotation)
    elif get_origin(annotation) is list and get_origin(get_args(annotation)[0]) is Literal:
        field_type, options = "multiselect", get_args(get_args(annotation)[0])
    else:
        extra = info.json_schema_extra if isinstance(info.json_schema_extra, dict) else {}
        field_type = extra.get("input", "text")  # type: ignore[assignment]

    min_length = _constraint(info, MinLen)
    labels = option_labels or {}
    return {
        "name": name,
        "type": field_type,
        "label": translate(f"{key}.{name}"),
        "required": bool(min_length) or field_type in ("select", "multiselect"),
        "min_length": min_length,
        "max_length": _constraint(info, MaxLen),
        "pattern": {"email": EMAIL_PATTERN, "tel": PHONE_PATTERN}.get(field_type),
        "options": [
            {
                "value": option,
                "label": labels.get(option) or translate(f"{key}.{name}.{option}"),
            }
            for option in options
        ],
    }


def describe_group(group: type[SettingsGroup], value: SettingsGroup) -> SettingsGroupDescription:
    """The group as the admin form sees it, in the request language."""
    return SettingsGroupDescription.model_validate(
        {
            "name": group.group,
            "title": translate(f"settings.{group.group}.title"),
            "fields": [
                describe_field(name, info, f"settings.{group.group}", group.option_labels(name))
                for name, info in group.model_fields.items()
            ],
            "values": value.model_dump(mode="json"),
        }
    )
