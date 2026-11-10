from dataclasses import asdict, dataclass

from app.core.i18n import has_translation, translate
from app.core.mail.layout import render_html


@dataclass(frozen=True)
class EmailMessage:
    to: str
    subject: str
    text: str
    # Optional HTML version (render_html); the text is always sent with it
    html: str | None = None

    def to_dict(self) -> dict[str, str | None]:
        """JSON-friendly form, e.g. for a task queue."""
        return asdict(self)


def render_mail(name: str, to: str, language: str | None = None, **params) -> EmailMessage:
    """A message from the "mail" translations: "<name>.subject" and "<name>.body".

    The HTML version is built from the same text; with a ``link`` parameter the line
    holding it becomes a button labelled "<name>.button".
    """
    subject = translate(f"mail.{name}.subject", language, **params)
    text = translate(f"mail.{name}.body", language, **params)
    button_key = f"mail.{name}.button"
    return EmailMessage(
        to=to,
        subject=subject,
        text=text,
        html=render_html(
            text,
            subject,
            link=params.get("link"),
            button=translate(button_key, language) if has_translation(button_key) else None,
            language=language,
        ),
    )
