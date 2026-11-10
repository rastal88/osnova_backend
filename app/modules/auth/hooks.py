"""What other modules do when an account is deleted.

The auth module knows nothing about files or notifications; a module that keeps
data of a user registers a hook that removes it (rows and anything outside the
database, like stored file contents) before the user row goes.
"""

from collections.abc import Awaitable, Callable

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.models import User

DeleteHook = Callable[[AsyncSession, User], Awaitable[None]]

delete_hooks: list[DeleteHook] = []


def on_user_delete(hook: DeleteHook) -> None:
    if hook not in delete_hooks:  # an app created twice (tests) registers it once
        delete_hooks.append(hook)
