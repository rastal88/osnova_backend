import logging
from typing import Any

from fastapi import APIRouter, Body, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError

from app.config import config
from app.core.errors import AppError
from app.core.forms.delivery import deliver, make_record, receivers
from app.core.forms.schema import (
    HONEYPOT_FIELD,
    Form,
    FormDescription,
    FormSubmitResponse,
    build_model,
    describe,
)
from app.core.i18n import get_language, translate
from app.core.rate_limit import RateLimiter, parse_limit
from app.forms import FORMS

logger = logging.getLogger(__name__)

forms_by_name: dict[str, Form] = {form.name: form for form in FORMS}

rate_limit = parse_limit(config.FORMS_RATE_LIMIT)
limiter = RateLimiter(*rate_limit) if rate_limit else None

forms_router = APIRouter(prefix="/forms", tags=["Forms"])


def _get_form(name: str) -> Form:
    form = forms_by_name.get(name)
    if form is None:
        raise AppError(404, "form_not_found")
    return form


def _check_rate_limit(form: Form, request: Request):
    if limiter is None:
        return
    # Behind a proxy the client address is correct only with uvicorn
    # --proxy-headers and FORWARDED_ALLOW_IPS set to the proxy address
    client = request.client.host if request.client else "unknown"
    retry_after = limiter.hit(f"{form.name}:{client}")
    if retry_after is not None:
        raise AppError(429, "too_many_requests", headers={"Retry-After": str(retry_after)})


@forms_router.get("/{name}")
async def get_form(name: str) -> FormDescription:
    return describe(_get_form(name))


@forms_router.post("/{name}")
async def submit_form(
    request: Request, name: str, payload: dict[str, Any] = Body(...)
) -> FormSubmitResponse:
    form = _get_form(name)
    _check_rate_limit(form, request)
    success = FormSubmitResponse(message=translate(f"forms.{form.name}.success"))

    if payload.pop(HONEYPOT_FIELD, None):
        # Answer as usual, so the bot does not learn it was caught
        logger.info("Form %s: honeypot filled, submission dropped", form.name)
        return success

    try:
        data = build_model(form).model_validate(payload)
    except ValidationError as exc:
        raise RequestValidationError(exc.errors()) from exc

    record = make_record(form.name, data.model_dump(), get_language())
    # Stored first: if that fails, the visitor sees an error and can send again
    for receiver in receivers:
        await receiver(record, request)
    await run_in_threadpool(deliver, record)
    return success
