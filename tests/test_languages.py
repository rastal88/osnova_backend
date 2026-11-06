import pytest

from app.config import Settings
from app.core.languages import LanguageConfigError, load_languages


def load(languages: str, default: str = "en"):
    return load_languages(Settings(LANGUAGES=languages, DEFAULT_LANGUAGE=default))


def test_parses_enabled_languages_in_order():
    result = load(" RU, en ,ru", default="RU")
    assert result.codes == ("ru", "en")
    assert result.default == "ru"


@pytest.mark.parametrize(
    ("languages", "default"),
    [
        ("", "en"),
        ("en,xx", "en"),
        ("ru", "en"),
    ],
)
def test_rejects_invalid_config(languages, default):
    with pytest.raises(LanguageConfigError):
        load(languages, default)
