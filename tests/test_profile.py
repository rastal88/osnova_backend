import logging

import pytest

from app import create_app
from app.core.profile import profile_warnings


@pytest.mark.parametrize(
    ("profile", "modules"),
    [
        ("minimal", []),
        ("standard", ["db", "auth"]),
        ("scalable", ["db"]),
    ],
)
def test_matching_profile_has_no_warnings(profile, modules):
    assert profile_warnings(profile, modules) == []


def test_minimal_with_modules_warns():
    (warning,) = profile_warnings("minimal", ["db", "auth"])
    assert "APP_PROFILE=minimal" in warning
    assert "db, auth" in warning


@pytest.mark.parametrize("profile", ["standard", "scalable"])
def test_profile_without_database_warns(profile):
    (warning,) = profile_warnings(profile, ["tasks"])
    assert f"APP_PROFILE={profile}" in warning
    assert "DATABASE_URL" in warning


def test_app_start_logs_no_warning_for_matching_setup(caplog):
    with caplog.at_level(logging.WARNING, logger="app.core.profile"):
        create_app()
    assert caplog.records == []
