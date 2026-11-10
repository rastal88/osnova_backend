from typing import Literal

from pydantic import BaseModel

from app.config import config
from app.core.capabilities import capabilities, oauth_providers
from app.core.languages import get_languages
from app.core.settings import settings
from app.settings import SiteSettings


class BootstrapApplication(BaseModel):
    name: str
    version: str
    contact_email: str
    contact_phone: str


class BootstrapLanguage(BaseModel):
    code: str
    name: str


class BootstrapI18n(BaseModel):
    languages: list[BootstrapLanguage]
    default: str


class BootstrapFeatures(BaseModel):
    authentication: bool
    admin: bool
    files: bool
    notifications: bool
    background_tasks: bool


class BootstrapResponse(BaseModel):
    application: BootstrapApplication
    profile: Literal["minimal", "standard", "scalable"]
    i18n: BootstrapI18n
    features: BootstrapFeatures
    # Sign-in providers to show as buttons, e.g. ["google"]
    auth_providers: list[str]
    # Interactive API docs are served at /docs (only with DEBUG)
    api_docs: bool


def get_bootstrap_config() -> BootstrapResponse:
    site = settings.get(SiteSettings)
    languages = get_languages()
    return BootstrapResponse(
        application=BootstrapApplication(
            name=site.name,
            version=config.APP_VERSION,
            contact_email=site.contact_email,
            contact_phone=site.contact_phone,
        ),
        profile=config.APP_PROFILE,
        i18n=BootstrapI18n(
            languages=[
                BootstrapLanguage(code=lang.code, name=lang.name) for lang in languages.enabled
            ],
            default=languages.default,
        ),
        features=BootstrapFeatures(
            authentication=capabilities.authentication,
            admin=capabilities.admin,
            files=capabilities.files,
            notifications=capabilities.notifications,
            background_tasks=capabilities.background_tasks,
        ),
        auth_providers=oauth_providers(config),
        api_docs=config.DEBUG,
    )
