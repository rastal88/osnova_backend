"""`make init`: .env for the quick start from .env.example."""

import stat

from scripts import init_env

EXAMPLE = """# --- Application ---
APP_PROFILE=minimal
AUTH_ENABLED=false
SECRET_KEY=change-me
# POSTGRES_PASSWORD=osnova
# RUN_MIGRATIONS=true
# AUTH_ENABLED_NOTE=keep
"""


def test_sets_values_uncomments_and_keeps_the_rest():
    text = init_env.render(
        EXAMPLE,
        {"APP_PROFILE": "standard", "POSTGRES_PASSWORD": "pw", "SECRET_KEY": "s", "NEW": "1"},
    )
    lines = text.splitlines()
    assert "APP_PROFILE=standard" in lines
    assert "SECRET_KEY=s" in lines
    # A commented example line becomes a setting
    assert "POSTGRES_PASSWORD=pw" in lines
    assert "# POSTGRES_PASSWORD=osnova" not in lines
    # Untouched
    assert "AUTH_ENABLED=false" in lines
    assert "# RUN_MIGRATIONS=true" in lines
    assert "# AUTH_ENABLED_NOTE=keep" in lines
    assert lines[0] == "# --- Application ---"
    # Missing from the example: added at the end
    assert lines[-1] == "NEW=1"


def test_the_real_example_gets_every_quick_start_value():
    example = (init_env.ROOT / ".env.example").read_text()
    values = init_env.quick_start_values()
    lines = init_env.render(example, values).splitlines()
    for key, value in values.items():
        assert lines.count(f"{key}={value}") == 1, key
    assert len(values["SECRET_KEY"]) >= 32
    # Every key is in the example already: nothing appended
    assert len(lines) == len(example.splitlines())


def test_secrets_differ_every_time():
    first, second = init_env.quick_start_values(), init_env.quick_start_values()
    assert first["SECRET_KEY"] != second["SECRET_KEY"]
    assert first["POSTGRES_PASSWORD"] != second["POSTGRES_PASSWORD"]


def test_writes_env_once_readable_by_the_owner(tmp_path, monkeypatch):
    (tmp_path / ".env.example").write_text(EXAMPLE)
    monkeypatch.setattr(init_env, "ROOT", tmp_path)

    assert init_env.main() == 0
    env = tmp_path / ".env"
    assert "APP_PROFILE=standard" in env.read_text()
    assert stat.S_IMODE(env.stat().st_mode) == 0o600

    # A second run leaves it as it is
    env.write_text("MINE=1\n")
    assert init_env.main() == 1
    assert env.read_text() == "MINE=1\n"
