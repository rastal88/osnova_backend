import typer
import asyncio
from app.core.database import get_async_session
from app.core.user.auth import get_user_manager



app = typer.Typer()

# @app.command()
# def createsuperuser(email: str, password: str):
#     """Создает суперпользователя в системе."""
#     async def _create():
#         async for session in get_async_session():
#             user_manager = await get_user_manager(session)
#             user = await user_manager.create_superuser(email=email, password=password)
#             print(f"Суперпользователь {user.email} создан.")
#
#     asyncio.run(_create())


if __name__ == "__main__":
    app()