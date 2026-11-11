"""Description of a settings group for the generated admin form.

The description has the same shape as a form description (app/core/forms), so
the frontend renders the edit form with the same SchemaForm. Field types:

- ``str`` → text (``Field(json_schema_extra={"input": "textarea"})`` for others;
  OptionalEmail / OptionalPhone set email / tel);
- ``bool`` → checkbox; ``int`` → number (``ge`` / ``le`` give the range);
- ``Literal[...]`` → select; ``list[Literal[...]]`` → multiselect.

Texts come from the "settings" section of app/core/locales/*.json:
"<group>.title", "<group>.<field>", an optional hint "<group>.<field>.help" and, for
options, "<group>.<field>.<option>" (or the group's ``option_labels``).
"""

from typing import Any, Literal, get_args, get_origin

from annotated_types import Ge, Le, MaxLen, MinLen
from pydantic import BaseModel
from pydantic.fields import FieldInfo

from app.core.forms.schema import FieldType, FormFieldDescription
from app.core.i18n import has_translation, translate
from app.core.patterns import EMAIL_PATTERN, PHONE_PATTERN
from app.core.settings.base import SettingsGroup, mask_secrets


class SettingsGroupDescription(BaseModel):
    name: str
    title: str
    fields: list[FormFieldDescription]
    values: dict[str, Any]
    # The signed-in user may change it (set by the admin API)
    editable: bool = False


def _constraint(info: FieldInfo, kind: type) -> int | None:
    names = {MinLen: "min_length", MaxLen: "max_length", Ge: "ge", Le: "le"}
    for item in info.metadata:
        if isinstance(item, kind):
            return getattr(item, names[kind])
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
    elif annotation is int:
        field_type = "number"
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
        "required": bool(min_length) or field_type in ("select", "multiselect", "number"),
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
        "min_value": _constraint(info, Ge),
        "max_value": _constraint(info, Le),
        "help": translate(f"{key}.{name}.help") if has_translation(f"{key}.{name}.help") else None,
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
            # Secrets are never sent back in clear
            "values": mask_secrets(group, value.model_dump(mode="json")),
        }
    )
