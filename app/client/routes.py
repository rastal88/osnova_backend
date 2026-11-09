from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.modules.auth.dependencies import current_user
from app.modules.auth.models import User
from app.modules.auth.roles import Role

# Every endpoint of the client area requires a signed-in, active user.
client_router = APIRouter(dependencies=[Depends(current_user)])


class ClientSummary(BaseModel):
    email: str
    role: Role


@client_router.get("/summary")
async def client_summary(user: User = Depends(current_user)) -> ClientSummary:
    """Example endpoint: data for the client dashboard."""
    return ClientSummary(email=user.email, role=user.role)
