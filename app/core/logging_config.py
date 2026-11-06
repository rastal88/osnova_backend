import logging
import sys

from app.core.request_id import RequestIdFilter


def setup_logging():
    handler = logging.StreamHandler(sys.stdout)
    handler.addFilter(RequestIdFilter())
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - [%(request_id)s] %(message)s",
        handlers=[handler],
    )
    # Requests are logged by app.core.middlewares with the request id
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("celery").setLevel(logging.INFO)
