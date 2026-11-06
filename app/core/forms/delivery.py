"""Where submitted forms go.

Minimal profile ships stubs only: "log" writes the submission to the
application log, "file" also appends it to FORMS_FILE as one JSON line.
Real channels (email, Telegram, webhook) are added as new backends here.
"""

import json
import logging
import threading
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from app.config import config

logger = logging.getLogger(__name__)
_file_lock = threading.Lock()

Backend = Callable[[dict], None]


def _log(record: dict) -> None:
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


def deliver(form: str, data: dict, language: str) -> None:
    record = {
        "form": form,
        "submitted_at": datetime.now(UTC).isoformat(),
        "language": language,
        "data": data,
    }
    BACKENDS[config.FORMS_DELIVERY](record)
