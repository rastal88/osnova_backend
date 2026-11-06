import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.config import config
from app.core.errors import error_response
from app.core.i18n import LanguageMiddleware

logger = logging.getLogger(__name__)


def add_middlewares(app: FastAPI):
    origins = [o.strip() for o in config.CORS_ORIGINS.split(",") if o.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        logger.info(f"Request: {request.method} {request.url}")
        try:
            response = await call_next(request)
        except Exception:
            logger.exception("Unhandled error")
            return error_response(500, "internal_error")
        logger.info(f"Response: {response.status_code}")
        return response

    # Outermost, so every response (errors included) is in the request language
    app.add_middleware(LanguageMiddleware)
