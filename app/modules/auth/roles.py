from collections.abc import Collection
from enum import Enum

from app.modules.auth.permissions import ADMIN_ACCESS


class Role(str, Enum):
    """The roles every project starts with; more are rows of the "roles" table.

    root has every permission and is not edited, user is given at sign-up.
    """

    ROOT = "root"
    MODERATOR = "moderator"
    USER = "user"


class Area(str, Enum):
    """Parts of the interface: the public area needs no sign-in and is not listed."""

    ADMIN = "admin"
    USER = "user"


def user_areas(permissions: Collection[str], admin_enabled: bool) -> list[Area]:
    """Areas open with these permissions; the first one is where the user lands after
    sign-in. Whoever works in the admin area can also use the user area."""
    if admin_enabled and ADMIN_ACCESS in permissions:
        return [Area.ADMIN, Area.USER]
    return [Area.USER]
