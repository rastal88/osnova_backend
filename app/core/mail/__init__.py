"""Sending email.

Build a message with ``render_mail`` (texts from the "mail" section of
app/core/locales/*.json, in the request language) and send it with
``await send_mail(message)``. Admin → Settings → Mail (MailSettings; MAIL_* and SMTP_*
in .env are the initial values) picks the delivery:

- ``console`` (default): the text is written to the log — for development;
- ``smtp``: sent through the SMTP server (standard library, no extra packages).

Messages carry the text and an HTML version in one layout (layout.html: site name,
heading, a button for the link). ``render_mail`` builds both; for a message made
by hand pass ``html=render_html(text, subject, link=...)``.

By default ``send_mail`` starts sending in a thread and returns at once; with the
background tasks module it puts the message on the Celery queue instead (see
app/modules/tasks), which also retries. Either way a slow mail server never delays
a response. Failures are logged, not raised: a reset or verification request must
not fail because the mail server is down.
"""

from app.core.mail.layout import render_html
from app.core.mail.message import EmailMessage, render_mail
from app.core.mail.sending import deliver, send_mail, use_dispatcher

__all__ = ["EmailMessage", "deliver", "render_html", "render_mail", "send_mail", "use_dispatcher"]
