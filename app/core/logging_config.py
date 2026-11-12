"""Logs to stdout: readable text (default) or one JSON object per line for log
collectors (Loki, ELK, cloud logging), with LOG_FORMAT=json. LOG_LEVEL sets the level.

Every line carries the request id (app/core/request_id.py). Fields passed with
``logger.info(..., extra={"status": 200})`` become JSON keys. The web server
(uvicorn) and the Celery worker write through the same handler, so their lines
have the same format.
"""

import json
import logging
import sys
import traceback
from datetime import UTC, datetime

from app.config import config
from app.core.request_id import RequestIdFilter

TEXT_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - [%(request_id)s] %(message)s"

# Attributes every LogRecord has; anything else came with `extra`
_STANDARD = set(vars(logging.LogRecord("", 0, "", 0, "", None, None))) | {
    "message",
    "asctime",
    "request_id",
    "taskName",
}


class JsonFormatter(logging.Formatter):
    """One JSON object per record: time (UTC), level, logger, message, request_id,
    the `extra` fields and the traceback of an exception."""

    def format(self, record: logging.LogRecord) -> str:
        entry = {
            "time": datetime.fromtimestamp(record.created, UTC).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": getattr(record, "request_id", "-"),
        }
        for key, value in vars(record).items():
            if key not in _STANDARD and not key.startswith("_"):
                entry[key] = value
        if record.exc_info:
            entry["exception"] = "".join(traceback.format_exception(*record.exc_info)).rstrip()
        # Values that are not JSON (e.g. a UUID) are written as text
        return json.dumps(entry, ensure_ascii=False, default=str)


def setup_logging() -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.addFilter(RequestIdFilter())
    if config.LOG_FORMAT == "json":
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(logging.Formatter(TEXT_FORMAT))
    logging.basicConfig(level=config.LOG_LEVEL.upper(), handlers=[handler], force=True)

    # uvicorn and Celery set up loggers of their own: send them through this handler
    for name in ("uvicorn", "uvicorn.error", "celery"):
        logger = logging.getLogger(name)
        logger.handlers.clear()
        logger.propagate = True
    # Requests are logged by app.core.middlewares with the request id
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("celery").setLevel(logging.INFO)
