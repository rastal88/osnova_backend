import pytest

from app.modules.auth.permissions import ADMIN_ACCESS
from app.modules.auth.roles import Area, user_areas

pytestmark = pytest.mark.modules("auth")


def test_admin_access_lands_in_admin():
    assert user_areas({ADMIN_ACCESS, "leads.read"}, admin_enabled=True) == [Area.ADMIN, Area.USER]


def test_without_admin_access_only_the_user_area():
    assert user_areas({"leads.read"}, admin_enabled=True) == [Area.USER]
    assert user_areas(set(), admin_enabled=True) == [Area.USER]


def test_admin_disabled_leaves_only_the_user_area():
    assert user_areas({ADMIN_ACCESS}, admin_enabled=False) == [Area.USER]
