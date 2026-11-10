"""Where submitted forms go.

Every submission goes to the stub FORMS_DELIVERY: "log" writes it to the
application log, "file" also appends it to FORMS_FILE as one JSON line.
Modules add receivers (``add_receiver``): with the admin, the leads module
stores submissions in the database and delivers them to the configured channels;
then the log gets only the form name, so personal data stays out of the logs.
"""

import json
import logging
import threading
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from pathlib import Path

from fastapi import Request

from app.config import config

logger = logging.getLogger(__name__)
_file_lock = threading.Lock()

Backend = Callable[[dict], None]
Receiver = Callable[[dict, Request], Awaitable[None]]


def _log(record: dict) -> None:
    if receivers:
        logger.info("Form submitted: %s (handed to %d receivers)", record["form"], len(receivers))
        return
    logger.info("Form submitted: %s", json.dumps(record, ensure_ascii=False))


def _file(record: dict) -> None:
    _log(record)
    path = Path(config.FORMS_FILE)
    line = json.dumps(record, ensure_ascii=False) + "\n"
    with _file_lock:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as file:
            file.write(line)


BACKENDS: dict[str, Backend] = {"log": _log, "file": _file}


receivers: list[Receiver] = []


def add_receiver(receiver: Receiver) -> None:
    """Also hand every valid submission to ``receiver`` (an error fails the request)."""
    if receiver not in receivers:  # an app created twice (tests) registers it once
        receivers.append(receiver)


def make_record(form: str, data: dict, language: str) -> dict:
    return {
        "form": form,
        "submitted_at": datetime.now(UTC).isoformat(),
        "language": language,
        "data": data,
    }


def deliver(record: dict) -> None:
    BACKENDS[config.FORMS_DELIVERY](record)
