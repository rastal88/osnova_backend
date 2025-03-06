from fastapi import FastAPI
from .logging import setup_logging
from .config import settings

app = FastAPI()

setup_logging()
logger = logging.getLogger(__name__)

@app.get("/")
def read_root():
    return {"message": "Hello World", "config_mode": settings.CONFIG_MODE}

@app.get("/config")
def get_config():
    return {
        "database_url": settings.DATABASE_URL,
        "debug": settings.DEBUG,
        "config_mode": settings.CONFIG_MODE
    }

