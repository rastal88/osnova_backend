import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import config

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
            return JSONResponse(status_code=500, content={"detail": "Internal server error."})
        logger.info(f"Response: {response.status_code}")
        return response
