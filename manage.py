import asyncio
import typer

from fastapi_users import exceptions as fastapi_users_exceptions
from app.core.database import get_async_session
from app.core.user.utils import UserManager, get_user_db


app = typer.Typer()

@app.command()
def createroot(
    email: str = typer.Option(..., "--email", prompt=True, help="Email app's root"),
    password: str = typer.Option(..., "--password", prompt=True, hide_input=True, help="Password app's root"),
):
    """Creates a superuser in the database."""

    async def _create_superuser():
        async for session in get_async_session():
            async for user_db in get_user_db(session):
                manager = UserManager(user_db)

                try:
                    await manager.get_by_email(email)
                    typer.echo(f"⚠ A user with this email already exists.")
                    return
                except fastapi_users_exceptions.UserNotExists:
                    pass

                user = await manager.create_superuser({"email": email, "password": password})
                typer.echo(f"✅ Root {user.email} has been successfully created.")

    asyncio.run(_create_superuser())


@app.command()
def hello(name: str):
    print(f'Hello {name}')


if __name__ == "__main__":
    app()
