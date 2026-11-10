from app.modules.auth.roles import Area, Role, user_areas


def test_admin_roles_land_in_admin():
    for role in (Role.ROOT, Role.MODERATOR):
        assert user_areas(role, admin_enabled=True) == [Area.ADMIN, Area.USER]


def test_user_sees_only_client_area():
    assert user_areas(Role.USER, admin_enabled=True) == [Area.USER]


def test_no_admin_area_without_admin_module():
    assert user_areas(Role.ROOT, admin_enabled=False) == [Area.USER]
