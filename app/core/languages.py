"""Interface languages.

The backend is the source of truth for languages: the frontend receives the
enabled list and the default from /bootstrap. To add a language, add it to
AVAILABLE_LANGUAGES (and its translations), then list it in LANGUAGES.
"""

from dataclasses import dataclass

from app.config import Settings, config

# Languages the template ships with: code -> native name.
AVAILABLE_LANGUAGES: dict[str, str] = {
    "en": "English",
    "ru": "Русский",
}


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


def load_languages(settings: Settings) -> Languages:
    raw = (c.strip().lower() for c in settings.LANGUAGES.split(","))
    codes = list(dict.fromkeys(c for c in raw if c))
    default = settings.DEFAULT_LANGUAGE.strip().lower()

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


languages = load_languages(config)
