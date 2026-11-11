"""Permissions: named actions a role allows, e.g. "leads.read" or "users.block".

A module declares its permissions where it uses them:

    LEADS_READ = permission("leads.read")
    router = APIRouter(dependencies=[Depends(require(LEADS_READ))])

Only declared names exist, so a typo fails at import. Roles are stored in the
database as sets of these names (app/modules/auth/models.py); the root role has
every permission, including the ones declared later. Names a role keeps from a
module that is switched off are ignored.

No database imports here: the names are also used by schemas and settings.
"""

import re

_NAME = re.compile(r"[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)+")
_declared: set[str] = set()


def permission(name: str) -> str:
    """Declare a permission as "<area>.<action>" and return its name."""
    if not _NAME.fullmatch(name):
        raise ValueError(f"Permission name must look like 'area.action': {name!r}")
    _declared.add(name)
    return name


def all_permissions() -> frozenset[str]:
    """Every permission declared by the enabled modules."""
    return frozenset(_declared)


def check_declared(*names: str) -> None:
    if unknown := [name for name in names if name not in _declared]:
        raise ValueError(f"Unknown permission: {', '.join(unknown)}")


# Opens the admin area; its sections ask for their own permissions on top
ADMIN_ACCESS = permission("admin.access")
