"""Readiness: can this process serve requests right now?

GET /health answers while the process runs (liveness). GET /ready also checks
what the enabled modules depend on — the database, Redis sessions, the task broker — so a load
balancer or orchestrator sends traffic only to replicas that can serve it.
Modules register their checks with ``add_check`` (the core imports no module).
"""

import asyncio
import logging
from collections.abc import Awaitable, Callable

logger = logging.getLogger(__name__)

Check = Callable[[], Awaitable[None]]
TIMEOUT_SECONDS = 3

checks: dict[str, Check] = {}


def add_check(name: str, check: Check) -> None:
    """`check` raises (or takes longer than TIMEOUT_SECONDS) when the dependency is down."""
    checks[name] = check


async def _run(name: str, check: Check) -> bool:
    try:
        await asyncio.wait_for(check(), TIMEOUT_SECONDS)
        return True
    except Exception:
        logger.warning("Readiness check %s failed", name, exc_info=True)
        return False


async def run_checks() -> dict[str, bool]:
    results = await asyncio.gather(*(_run(name, check) for name, check in checks.items()))
    return dict(zip(checks, results, strict=True))
