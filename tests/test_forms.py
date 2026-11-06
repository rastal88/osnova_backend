import json

import pytest

from app.config import config
from app.core.forms import Form, FormField
from app.core.forms.schema import build_model
from app.core.i18n import catalogs, translate
from app.forms import FORMS

RU = {"Accept-Language": "ru"}
VALID = {
    "name": "Ann",
    "email": "ann@example.com",
    "phone": "+1 (555) 010-20",
    "topic": "order",
    "message": "Hello, I would like to order.",
    "consent": True,
}


def test_every_form_text_is_translated():
    for form in FORMS:
        keys = ["title", "submit", "success"]
        for item in form.fields:
            keys.append(item.name)
            keys.extend(f"{item.name}.{option}" for option in item.options)
        for key in keys:
            assert f"{form.name}.{key}" in catalogs["en"]["forms"], (form.name, key)


def test_select_needs_options():
    with pytest.raises(ValueError):
        FormField("topic", type="select")


@pytest.mark.anyio
async def test_describe_form(client):
    response = await client.get("/api/v1/forms/contact", headers=RU)
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Связаться с нами"
    fields = {item["name"]: item for item in data["fields"]}
    assert list(fields) == ["name", "email", "phone", "topic", "message", "consent"]
    assert fields["name"] == {
        "name": "name",
        "type": "text",
        "label": "Имя",
        "required": True,
        "min_length": 2,
        "max_length": 100,
        "pattern": None,
        "options": [],
    }
    assert fields["email"]["pattern"]
    assert fields["consent"]["required"] is True
    assert fields["topic"]["options"][0] == {"value": "question", "label": "Вопрос"}


@pytest.mark.anyio
async def test_unknown_form(client):
    response = await client.get("/api/v1/forms/missing")
    assert response.status_code == 404
    assert response.json() == {"code": "form_not_found", "message": "Form not found."}
    response = await client.post("/api/v1/forms/missing", json={})
    assert response.status_code == 404


@pytest.mark.anyio
async def test_submit_valid_form(client, caplog):
    caplog.set_level("INFO", logger="app.core.forms.delivery")
    response = await client.post(
        "/api/v1/forms/contact", json={**VALID, "name": "  Ann  ", "extra": "x"}, headers=RU
    )
    assert response.status_code == 200
    assert response.json() == {"message": "Спасибо! Мы скоро свяжемся с вами."}
    [message] = [r.getMessage() for r in caplog.records if r.name == "app.core.forms.delivery"]
    record = json.loads(message.split(": ", 1)[1])
    assert record["form"] == "contact"
    assert record["language"] == "ru"
    assert record["data"] == {**VALID, "name": "Ann"}


@pytest.mark.anyio
async def test_submit_lists_field_errors(client):
    response = await client.post(
        "/api/v1/forms/contact",
        json={"name": " ", "email": "not-an-email", "topic": "spam", "message": "Hi"},
        headers=RU,
    )
    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "validation_error"
    assert body["fields"] == [
        {"field": "name", "code": "missing", "message": "Обязательное поле."},
        {"field": "email", "code": "email_invalid", "message": "Введите корректный email."},
        {"field": "topic", "code": "literal_error", "message": "Выберите один из вариантов."},
        {"field": "message", "code": "string_too_short", "message": "Минимум символов: 10."},
        {"field": "consent", "code": "missing", "message": "Обязательное поле."},
    ]


@pytest.mark.anyio
async def test_consent_must_be_checked(client):
    response = await client.post("/api/v1/forms/contact", json={**VALID, "consent": False})
    assert response.status_code == 422
    assert response.json()["fields"] == [
        {
            "field": "consent",
            "code": "must_be_checked",
            "message": "Please check this box to continue.",
        }
    ]


@pytest.mark.anyio
async def test_optional_fields_may_be_empty(client):
    response = await client.post(
        "/api/v1/forms/contact", json={**VALID, "phone": "", "topic": None}
    )
    assert response.status_code == 200


@pytest.mark.anyio
async def test_body_must_be_an_object(client):
    response = await client.post("/api/v1/forms/contact", json=["x"])
    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"


@pytest.mark.anyio
async def test_file_delivery(client, tmp_path, monkeypatch):
    path = tmp_path / "forms" / "submissions.jsonl"
    monkeypatch.setattr(config, "FORMS_DELIVERY", "file")
    monkeypatch.setattr(config, "FORMS_FILE", str(path))

    for _ in range(2):
        response = await client.post("/api/v1/forms/contact", json=VALID)
        assert response.status_code == 200

    lines = path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0])["data"] == VALID


def test_custom_pattern_and_optional_checkbox():
    model = build_model(
        Form(
            "custom",
            fields=(
                FormField("code", required=True, pattern=r"^[A-Z]{3}$"),
                FormField("subscribe", type="checkbox"),
            ),
        )
    )
    assert model.model_validate({"code": "ABC"}).model_dump() == {
        "code": "ABC",
        "subscribe": False,
    }
    with pytest.raises(Exception) as info:
        model.model_validate({"code": "abc"})
    assert info.value.errors()[0]["type"] == "string_pattern_mismatch"
    assert translate("validation.string_pattern_mismatch") == "Invalid format."


def test_form_cannot_use_honeypot_name():
    with pytest.raises(ValueError):
        Form("bad", fields=(FormField("website"),))


@pytest.mark.anyio
async def test_describe_names_honeypot(client):
    response = await client.get("/api/v1/forms/contact")
    assert response.json()["honeypot"] == "website"


@pytest.mark.anyio
async def test_filled_honeypot_is_dropped(client, caplog):
    caplog.set_level("INFO")
    response = await client.post("/api/v1/forms/contact", json={**VALID, "website": "spam.example"})

    assert response.status_code == 200
    assert response.json() == {"message": translate("forms.contact.success", "en")}
    assert not [r for r in caplog.records if r.name == "app.core.forms.delivery"]


@pytest.mark.anyio
async def test_empty_honeypot_is_delivered(client, caplog):
    caplog.set_level("INFO", logger="app.core.forms.delivery")
    response = await client.post("/api/v1/forms/contact", json={**VALID, "website": ""})

    assert response.status_code == 200
    assert [r for r in caplog.records if r.name == "app.core.forms.delivery"]


@pytest.mark.anyio
async def test_submissions_are_rate_limited(client):
    for _ in range(5):
        response = await client.post("/api/v1/forms/contact", json={})
        assert response.status_code == 422

    response = await client.post("/api/v1/forms/contact", json=VALID, headers=RU)
    assert response.status_code == 429
    assert response.json() == {
        "code": "too_many_requests",
        "message": "Слишком много запросов. Попробуйте позже.",
    }
    assert 1 <= int(response.headers["Retry-After"]) <= 60
