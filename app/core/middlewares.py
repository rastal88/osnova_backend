import logging
import time

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.config import config
from app.core.errors import error_response
from app.core.i18n import LanguageMiddleware
from app.core.request_id import HEADER as REQUEST_ID_HEADER
from app.core.request_id import RequestIdMiddleware, current_request_id

logger = logging.getLogger(__name__)


def add_middlewares(app: FastAPI):
    origins = [o.strip() for o in config.CORS_ORIGINS.split(",") if o.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=[REQUEST_ID_HEADER],
    )

    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        started = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            logger.exception("Unhandled error: %s %s", request.method, request.url.path)
            # The id lets a user report the error and support find it in the logs
            response = error_response(500, "internal_error", request_id=current_request_id.get())
        duration_ms = (time.perf_counter() - started) * 1000
        logger.info(
            "%s %s %s %.0fms", request.method, request.url.path, response.status_code, duration_ms
        )
        return response

    # So every response (errors included) is in the request language
    app.add_middleware(LanguageMiddleware)
    # Outermost, so the language middleware and every log line see the id
    app.add_middleware(RequestIdMiddleware)
