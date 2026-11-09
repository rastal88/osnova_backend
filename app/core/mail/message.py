from dataclasses import asdict, dataclass

from app.core.i18n import translate


@dataclass(frozen=True)
class EmailMessage:
    to: str
    subject: str
    text: str

    def to_dict(self) -> dict[str, str]:
        """JSON-friendly form, e.g. for a task queue."""
        return asdict(self)


def render_mail(name: str, to: str, language: str | None = None, **params) -> EmailMessage:
    """A message from the "mail" translations: "<name>.subject" and "<name>.body"."""
    return EmailMessage(
        to=to,
        subject=translate(f"mail.{name}.subject", language, **params),
        text=translate(f"mail.{name}.body", language, **params),
    )
