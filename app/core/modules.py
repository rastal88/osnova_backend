"""Module registry.

Every optional capability lives in its own package and exposes
``register(app) -> ShutdownHook | None``. A package is imported only when it
is enabled, so a disabled module costs nothing at runtime and its
dependencies (requirements/<module>.txt) do not have to be installed.

To remove a module from a project: delete its package, its entry below and
its requirements file.
"""

import importlib
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

from fastapi import FastAPI

from app.config import Settings

ShutdownHook = Callable[[], Awaitable[None]]


class ModuleConfigError(RuntimeError):
    pass


@dataclass(frozen=True)
class ModuleSpec:
    name: str
    path: str
    enabled: Callable[[Settings], bool]
    requires: tuple[str, ...] = field(default_factory=tuple)
    hint: str = ""


MODULES: tuple[ModuleSpec, ...] = (
    ModuleSpec(
        name="db",
        path="app.modules.db",
        enabled=lambda c: bool(c.DATABASE_URL),
        hint="set DATABASE_URL",
    ),
    ModuleSpec(
        name="auth",
        path="app.modules.auth",
        enabled=lambda c: c.AUTH_ENABLED,
        requires=("db",),
        hint="set AUTH_ENABLED=true",
    ),
    ModuleSpec(
        name="user_flow",
        path="app.user_flow",
        enabled=lambda c: c.AUTH_ENABLED,
        requires=("auth",),
    ),
    ModuleSpec(
        name="admin",
        path="app.modules.admin",
        enabled=lambda c: c.ADMIN_ENABLED,
        requires=("auth",),
        hint="set ADMIN_ENABLED=true",
    ),
    ModuleSpec(
        name="files",
        path="app.modules.files",
        enabled=lambda c: c.FILES_ENABLED,
        requires=("auth",),
        hint="set FILES_ENABLED=true",
    ),
    ModuleSpec(
        name="tasks",
        path="app.modules.tasks",
        enabled=lambda c: c.BACKGROUND_TASKS_ENABLED,
        hint="set BACKGROUND_TASKS_ENABLED=true",
    ),
)


def resolve_enabled(settings: Settings) -> list[ModuleSpec]:
    by_name = {spec.name: spec for spec in MODULES}
    enabled = [spec for spec in MODULES if spec.enabled(settings)]
    enabled_names = {spec.name for spec in enabled}

    for spec in enabled:
        missing = [name for name in spec.requires if name not in enabled_names]
        if missing:
            hints = ", ".join(
                f"{name} ({by_name[name].hint})" if by_name[name].hint else name for name in missing
            )
            raise ModuleConfigError(f"Module '{spec.name}' requires: {hints}")

    return enabled


def load_modules(app: FastAPI, settings: Settings) -> list[ShutdownHook]:
    enabled = resolve_enabled(settings)
    hooks: list[ShutdownHook] = []
    for spec in enabled:
        module = importlib.import_module(spec.path)
        hook = module.register(app)
        if hook is not None:
            hooks.append(hook)
    app.state.modules = [spec.name for spec in enabled]
    return hooks
