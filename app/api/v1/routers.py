from fastapi import APIRouter
from app.api.v1.endpoints import example

router = APIRouter()
router.include_router(example.router, prefix="/examples", tags=["examples"])