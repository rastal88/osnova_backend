from enum import Enum


class Role(str, Enum):
    ROOT = "root"
    MODERATOR = "moderator"
    USER = "user"


class Area(str, Enum):
    """Parts of the interface: the public area needs no sign-in and is not listed."""

    ADMIN = "admin"
    USER = "user"


# Roles that work in the admin area; they can also use the user area.
ADMIN_ROLES = (Role.ROOT, Role.MODERATOR)


def user_areas(role: Role, admin_enabled: bool) -> list[Area]:
    """Areas open to a role; the first one is where the user lands after sign-in."""
    if admin_enabled and role in ADMIN_ROLES:
        return [Area.ADMIN, Area.USER]
    return [Area.USER]
