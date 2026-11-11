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


async def rotate_secrets(session) -> dict[str, int]:
    """Encrypt every stored secret with the current SECRET_KEY; how many rows changed.

    Covers OAuth tokens, secret parameters of entities and secret settings of the
    enabled modules (app/modules/auth/encryption.py).
    """
    from sqlalchemy import select
    from sqlalchemy.orm.attributes import flag_modified

    import app as application
    from app.core.entities import entity_types
    from app.core.settings import secret_fields
    from app.modules.auth.encryption import rotate
    from app.modules.auth.models import OAuthAccount

    def rotated(values: dict, secret: set[str]) -> dict:
        return {
            key: rotate(value) if key in secret and isinstance(value, str) else value
            for key, value in values.items()
        }

    changed = {"oauth": 0, "entities": 0, "settings": 0}
    # The column type encrypts again with the current key when it is written
    for account in await session.scalars(select(OAuthAccount)):
        flag_modified(account, "access_token")
        flag_modified(account, "refresh_token")
        changed["oauth"] += 1

    enabled = set(application.app.state.modules)
    if "entities" in enabled:
        from app.modules.entities.models import Entity

        for entity in await session.scalars(select(Entity)):
            if (model := entity_types.get(entity.type)) is None:
                continue
            params = rotated(entity.params, secret_fields(model))
            if params != entity.params:
                entity.params = params
                changed["entities"] += 1

    if "settings" in enabled:
        from app.modules.settings.models import SettingsRecord
        from app.modules.settings.service import groups_by_name

        for record in await session.scalars(select(SettingsRecord)):
            if (group := groups_by_name.get(record.group)) is None:
                continue
            values = rotated(record.values, secret_fields(group))
            if values != record.values:
                record.values = values
                changed["settings"] += 1

    await session.commit()
    return changed


@app.command("rotate-secrets")
def rotate_secrets_command():
    """Encrypts stored secrets (channel tokens, OAuth tokens, secret settings) with the
    current SECRET_KEY: after moving the old key to OLD_SECRET_KEYS, and for values
    stored before encryption. Then the old key can be removed."""
    from app.modules.db.database import standalone_session

    async def _run():
        async with standalone_session() as session:
            return await rotate_secrets(session)

    for name, count in asyncio.run(_run()).items():
        typer.echo(f"{name}: {count}")


if __name__ == "__main__":
    app()
