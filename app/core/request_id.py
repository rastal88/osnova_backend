"""Request id: one value that ties together the logs and the response of a request.

The id comes from the X-Request-ID header (set by a proxy or the frontend) or is
generated. It is kept in a context variable, added to every log line by
RequestIdFilter and returned in the X-Request-ID response header.
"""

import logging
import re
import uuid
from contextvars import ContextVar

from starlette.datastructures import Headers, MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

HEADER = "X-Request-ID"
# Incoming ids end up in the logs, so only short, safe values are accepted
VALID_ID = re.compile(r"^[A-Za-z0-9._-]{1,128}$")

current_request_id: ContextVar[str] = ContextVar("current_request_id", default="-")


class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = current_request_id.get()
        return True


class RequestIdMiddleware:
    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        incoming = Headers(scope=scope).get(HEADER)
        request_id = incoming if incoming and VALID_ID.match(incoming) else uuid.uuid4().hex
        token = current_request_id.set(request_id)

        async def send_with_id(message: Message):
            if message["type"] == "http.response.start":
                MutableHeaders(scope=message)[HEADER] = request_id
            await send(message)

        try:
            await self.app(scope, receive, send_with_id)
        finally:
            current_request_id.reset(token)
