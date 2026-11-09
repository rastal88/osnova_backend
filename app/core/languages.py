"""Interface languages.

The backend is the source of truth for languages: the frontend receives the
enabled list and the default from /bootstrap. LANGUAGES / DEFAULT_LANGUAGE in
.env give the initial values; with the settings module they are changed in the
admin (group "languages"). To add a language, add it to AVAILABLE_LANGUAGES with
its translations (here and in the frontend).
"""

from dataclasses import dataclass
from typing import Literal

from pydantic import Field, field_validator
from pydantic_core import PydanticCustomError
from pydantic_core.core_schema import ValidationInfo

from app.config import Settings, config
from app.core.settings import SettingsGroup, settings

# Languages the template ships with: code -> native name.
AVAILABLE_LANGUAGES: dict[str, str] = {
    "en": "English",
    "ru": "Русский",
}

LanguageCode = Literal[tuple(AVAILABLE_LANGUAGES)]  # type: ignore[valid-type]


class LanguageConfigError(ValueError):
    pass


@dataclass(frozen=True)
class Language:
    code: str
    name: str


@dataclass(frozen=True)
class Languages:
    enabled: tuple[Language, ...]
    default: str

    @property
    def codes(self) -> tuple[str, ...]:
        return tuple(language.code for language in self.enabled)


def load_languages(source: Settings) -> Languages:
    """Languages from .env; raises on a wrong value, so the app does not start."""
    raw = (c.strip().lower() for c in source.LANGUAGES.split(","))
    codes = list(dict.fromkeys(c for c in raw if c))
    default = source.DEFAULT_LANGUAGE.strip().lower()

    if not codes:
        raise LanguageConfigError("LANGUAGES must list at least one language")
    unknown = [c for c in codes if c not in AVAILABLE_LANGUAGES]
    if unknown:
        raise LanguageConfigError(
            f"LANGUAGES has unknown codes {unknown}; available: {list(AVAILABLE_LANGUAGES)}"
        )
    if default not in codes:
        raise LanguageConfigError(f"DEFAULT_LANGUAGE={default!r} must be one of LANGUAGES {codes}")

    return Languages(
        enabled=tuple(Language(code=c, name=AVAILABLE_LANGUAGES[c]) for c in codes),
        default=default,
    )


env_languages = load_languages(config)


class LanguageSettings(SettingsGroup):
    group = "languages"

    enabled: list[LanguageCode] = Field(  # type: ignore[valid-type]
        default_factory=lambda: list(env_languages.codes), min_length=1
    )
    default: LanguageCode = env_languages.default  # type: ignore[valid-type]

    @field_validator("enabled")
    @classmethod
    def _unique(cls, value: list[str]) -> list[str]:
        return list(dict.fromkeys(value))

    @field_validator("default")
    @classmethod
    def _default_enabled(cls, value: str, info: ValidationInfo) -> str:
        if value not in info.data.get("enabled", [value]):
            raise PydanticCustomError("default_language_not_enabled", "Not an enabled language")
        return value

    @classmethod
    def option_labels(cls, field: str) -> dict[str, str] | None:
        return AVAILABLE_LANGUAGES


def get_languages() -> Languages:
    """Enabled languages and the default, as currently set."""
    current = settings.get(LanguageSettings)
    return Languages(
        enabled=tuple(Language(code=c, name=AVAILABLE_LANGUAGES[c]) for c in current.enabled),
        default=current.default,
    )
