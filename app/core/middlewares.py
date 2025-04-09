from fastapi import FastAPI, Request
from starlette.middleware.cors import CORSMiddleware
import logging

logger = logging.getLogger(__name__)

def add_middlewares(app: FastAPI):
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"], # Разрешает запросы из любых источников TODO: разрешить только для osnova_frontend
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        logger.info(f"Request: {request.method} {request.url}")
        try:
            response = await call_next(request)
        except Exception as e:
            logger.error(f"Error: {str(e)}")
            raise
        logger.info(f"Response: {response.status_code}")
        return response