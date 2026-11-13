import pytest
from pydantic import ValidationError

from app.core.forms import Form, FormField
from app.core.forms.schema import build_model
from app.core.languages import LanguageSettings, get_languages
from app.core.settings import settings
from app.core.settings.schema import describe_group
from app.modules.settings.models import SettingsRecord
from app.settings import SiteSettings
from tests.conftest import create_user, login

pytestmark = pytest.mark.modules("admin")


def test_defaults_come_from_env():
    assert settings.get(SiteSettings).name == "TestApp"
    assert settings.get(LanguageSettings).enabled == ["en", "ru"]


def test_language_default_must_be_enabled():
    with pytest.raises(ValidationError) as exc:
        LanguageSettings(enabled=["ru"], default="en")
    assert exc.value.errors()[0]["type"] == "default_language_not_enabled"


def test_languages_follow_settings():
    settings.set(LanguageSettings(enabled=["ru", "ru"], default="ru"))
    assert get_languages().codes == ("ru",)
    assert get_languages().default == "ru"


def test_describe_maps_field_types():
    description = describe_group(LanguageSettings, settings.get(LanguageSettings))
    fields = {item.name: item for item in description.fields}
    assert fields["enabled"].type == "multiselect"
    assert fields["default"].type == "select"
    assert [option.label for option in fields["default"].options] == ["English", "Русский"]

    site = describe_group(SiteSettings, settings.get(SiteSettings))
    types = {item.name: (item.type, item.required) for item in site.fields}
    assert types == {
        "name": ("text", True),
        "contact_email": ("email", False),
        "contact_phone": ("tel", False),
    }
    assert site.title == "Site"


def test_form_multiselect_field():
    form = Form(name="survey", fields=(FormField("tags", "multiselect", True, options=("a", "b")),))
    model = build_model(form)
    assert model.model_validate({"tags": ["a"]}).tags == ["a"]
    with pytest.raises(ValidationError):
        model.model_validate({"tags": []})


async def _signed_in(auth_client, role: str):
    client, session_factory = auth_client
    await create_user(session_factory, f"{role}@example.com", role)
    await login(client, f"{role}@example.com")
    return client


@pytest.mark.anyio
async def test_moderator_reads_but_cannot_change(auth_client):
    client = await _signed_in(auth_client, "moderator")

    response = await client.get("/api/v1/admin/settings")
    assert response.status_code == 200, response.text
    groups = response.json()
    # Groups with secrets (mail, protection) only for those who may change them
    assert [group["name"] for group in groups] == [
        "site",
        "languages",
        "retention",
        "files",
        "notifications",
    ]
    assert not any(group["editable"] for group in groups)

    response = await client.put("/api/v1/admin/settings/site", json={"name": "New"})
    assert response.status_code == 403
    assert (await client.put("/api/v1/admin/settings/mail", json={})).status_code == 403


@pytest.mark.anyio
async def test_user_has_no_access(auth_client):
    client = await _signed_in(auth_client, "user")
    assert (await client.get("/api/v1/admin/settings")).status_code == 403


@pytest.mark.anyio
async def test_root_changes_site_settings(auth_client):
    client = await _signed_in(auth_client, "root")

    response = await client.put(
        "/api/v1/admin/settings/site",
        json={"name": "Acme", "contact_email": "hi@acme.test"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["values"] == {
        "name": "Acme",
        "contact_email": "hi@acme.test",
        "contact_phone": "",
    }

    application = (await client.get("/api/v1/bootstrap")).json()["application"]
    assert application["name"] == "Acme"
    assert application["contact_email"] == "hi@acme.test"


@pytest.mark.anyio
async def test_invalid_values_return_field_errors(auth_client):
    client = await _signed_in(auth_client, "root")

    response = await client.put(
        "/api/v1/admin/settings/site", json={"name": "", "contact_email": "nope"}
    )
    assert response.status_code == 422
    codes = {item["field"]: item["code"] for item in response.json()["fields"]}
    assert codes == {"name": "string_too_short", "contact_email": "email_invalid"}

    response = await client.put(
        "/api/v1/admin/settings/languages", json={"enabled": ["ru"], "default": "en"}
    )
    assert response.status_code == 422
    assert response.json()["fields"][0]["field"] == "default"

    response = await client.put("/api/v1/admin/settings/unknown", json={})
    assert response.status_code == 404


@pytest.mark.anyio
async def test_languages_from_admin(auth_client):
    client = await _signed_in(auth_client, "root")

    response = await client.put(
        "/api/v1/admin/settings/languages", json={"enabled": ["ru"], "default": "ru"}
    )
    assert response.status_code == 200, response.text

    response = await client.get("/api/v1/bootstrap", headers={"Accept-Language": "en"})
    assert response.json()["i18n"] == {
        "languages": [{"code": "ru", "name": "Русский"}],
        "default": "ru",
    }
    assert response.headers["Content-Language"] == "ru"


@pytest.mark.anyio
async def test_stored_values_load_on_first_request(auth_client):
    client, session_factory = auth_client
    async with session_factory() as session:
        session.add(SettingsRecord(group="site", values={"name": "Stored", "removed": 1}))
        session.add(SettingsRecord(group="languages", values={"enabled": ["xx"]}))
        await session.commit()

    response = await client.get("/api/v1/bootstrap")
    assert response.json()["application"]["name"] == "Stored"
    # Invalid stored values fall back to the defaults
    assert response.json()["i18n"]["default"] == "en"
