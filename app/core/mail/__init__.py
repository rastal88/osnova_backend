"""Sending email.

Build a message with ``render_mail`` (texts from the "mail" section of
app/core/locales/*.json, in the request language) and send it with
``await send_mail(message)``. MAIL_BACKEND picks the delivery:

- ``console`` (default): the message is written to the log — for development;
- ``smtp``: sent through SMTP_HOST (standard library, no extra packages).

By default ``send_mail`` sends in a thread; with the background tasks module it
puts the message on the Celery queue instead (see app/modules/tasks), so a slow
mail server never delays a response. Failures are logged, not raised: a reset or
verification request must not fail because the mail server is down.
"""

from app.core.mail.message import EmailMessage, render_mail
from app.core.mail.sending import deliver, send_mail, use_dispatcher

__all__ = ["EmailMessage", "deliver", "render_mail", "send_mail", "use_dispatcher"]
