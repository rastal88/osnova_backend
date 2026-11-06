from typing import Literal

from pydantic import BaseModel

from app.config import config
from app.core.capabilities import capabilities
from app.core.languages import languages


class BootstrapApplication(BaseModel):
    name: str
    version: str


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


def get_bootstrap_config() -> BootstrapResponse:
    return BootstrapResponse(
        application=BootstrapApplication(name=config.APP_NAME, version=config.APP_VERSION),
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
    )
