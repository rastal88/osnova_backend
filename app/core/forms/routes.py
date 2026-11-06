from typing import Any

from fastapi import APIRouter, Body
from fastapi.concurrency import run_in_threadpool
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError

from app.core.errors import AppError
from app.core.forms.delivery import deliver
from app.core.forms.schema import Form, build_model, describe
from app.core.i18n import current_language, translate
from app.forms import FORMS

forms_by_name: dict[str, Form] = {form.name: form for form in FORMS}

forms_router = APIRouter(prefix="/forms", tags=["Forms"])


def _get_form(name: str) -> Form:
    form = forms_by_name.get(name)
    if form is None:
        raise AppError(404, "form_not_found")
    return form


@forms_router.get("/{name}")
async def get_form(name: str):
    return describe(_get_form(name))


@forms_router.post("/{name}")
async def submit_form(name: str, payload: dict[str, Any] = Body(...)):
    form = _get_form(name)
    try:
        data = build_model(form).model_validate(payload)
    except ValidationError as exc:
        raise RequestValidationError(exc.errors()) from exc

    await run_in_threadpool(deliver, form.name, data.model_dump(), current_language.get())
    return {"message": translate(f"forms.{form.name}.success")}
