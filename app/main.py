from fastapi import FastAPI
from app.core.config import settings
from app.api.v1.routers import router as api_router

app = FastAPI(title="Osnova API", version="1.0")

app.include_router(api_router, prefix="/api/v1")

@app.get("/")
def root():
    return {"message": "Welcome to Osnova API", "mode": settings.CONFIG_MODE}