"""Unified error format.

Every error response looks like {"code": "not_found", "message": "Not found."}:
`code` is stable for the frontend, `message` is in the request language.
Validation errors add `fields`: [{"field": "email", "code": "missing", "message": ...}].

Raise AppError(status, code, **params) with a code from the "errors" section
of app/core/locales/*.json. HTTPException is converted too: a detail that is a
known code (like the UPPER_SNAKE codes of fastapi-users) is used as the code,
otherwise the code comes from the status.
"""

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

from app.core.i18n import has_translation, translate

STATUS_CODES: dict[int, str] = {
    400: "bad_request",
    401: "unauthorized",
    403: "forbidden",
    404: "not_found",
    405: "method_not_allowed",
    409: "conflict",
    413: "payload_too_large",
    422: "validation_error",
    429: "too_many_requests",
    500: "internal_error",
}


class AppError(Exception):
    def __init__(self, status_code: int, code: str, **params):
        super().__init__(code)
        self.status_code = status_code
        self.code = code
        self.params = params


def error_response(
    status_code: int,
    code: str,
    fields: list[dict] | None = None,
    headers: dict[str, str] | None = None,
    **params,
) -> JSONResponse:
    content: dict = {"code": code, "message": translate(f"errors.{code}", **params)}
    if fields is not None:
        content["fields"] = fields
    return JSONResponse(status_code=status_code, content=content, headers=headers)


def _code_from_detail(detail) -> str | None:
    if isinstance(detail, dict):
        candidates = [detail.get("reason"), detail.get("code")]
    else:
        candidates = [detail]
    for candidate in candidates:
        if isinstance(candidate, str) and has_translation(f"errors.{candidate.lower()}"):
            return candidate.lower()
    return None


def _field_error(error: dict) -> dict:
    loc = [str(part) for part in error.get("loc", ())]
    if loc and loc[0] in ("body", "query", "path", "header", "cookie"):
        loc = loc[1:]
    key = f"validation.{error['type']}"
    message = translate(key, **error.get("ctx", {})) if has_translation(key) else error["msg"]
    return {"field": ".".join(loc), "code": error["type"], "message": message}


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    return error_response(exc.status_code, exc.code, **exc.params)


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    code = _code_from_detail(exc.detail) or STATUS_CODES.get(exc.status_code, "http_error")
    return error_response(exc.status_code, code, headers=getattr(exc, "headers", None))


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    fields = [_field_error(error) for error in exc.errors()]
    return error_response(422, "validation_error", fields=fields)


def add_exception_handlers(app: FastAPI):
    app.add_exception_handler(AppError, app_error_handler)
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
