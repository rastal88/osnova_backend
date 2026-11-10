import asyncio

import typer
from fastapi_users import exceptions as fastapi_users_exceptions

from app.modules.auth.manager import UserManager, get_user_db
from app.modules.db import get_async_session

# No local variables in tracebacks: they would print the password
app = typer.Typer(pretty_exceptions_show_locals=False)


@app.callback()
def main():
    """Project commands: python manage.py <command> --help"""


@app.command()
def createroot(
    email: str = typer.Option(..., "--email", prompt=True, help="Email app's root"),
    password: str = typer.Option(
        ..., "--password", prompt=True, hide_input=True, help="Password app's root"
    ),
):
    """Creates a superuser in the database."""

    async def _create_superuser():
        async for session in get_async_session():
            async for user_db in get_user_db(session):
                manager = UserManager(user_db)

                try:
                    await manager.get_by_email(email)
                    typer.echo("⚠ A user with this email already exists.")
                    return
                except fastapi_users_exceptions.UserNotExists:
                    pass

                user = await manager.create_superuser({"email": email, "password": password})
                typer.echo(f"✅ Root {user.email} has been successfully created.")

    asyncio.run(_create_superuser())


@app.command()
def cleanup():
    """Removes old rows (read notifications, never confirmed accounts): for cron in
    projects without Celery beat, which does the same every night."""
    from app.modules.db.cleanup import run_cleanup

    removed = asyncio.run(run_cleanup())
    for name, count in removed.items():
        typer.echo(f"{name}: {count}")


if __name__ == "__main__":
    app()
