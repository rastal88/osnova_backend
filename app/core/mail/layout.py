"""The HTML version of an email: its text put into layout.html.

The look (colours, fonts, the button) lives in layout.html and button.html next
to this file. Everything that comes from outside is escaped; a line of the text
that is exactly ``link`` becomes a button.
"""

from html import escape
from pathlib import Path
from string import Template

from app.core.i18n import get_language, translate
from app.core.settings import settings

_DIR = Path(__file__).parent
LAYOUT = Template((_DIR / "layout.html").read_text(encoding="utf-8"))
BUTTON = Template((_DIR / "button.html").read_text(encoding="utf-8"))
PARAGRAPH = '<p style="margin:0 0 16px;">{}</p>'


def render_html(
    text: str,
    subject: str,
    *,
    link: str | None = None,
    button: str | None = None,
    language: str | None = None,
) -> str:
    """`text` as paragraphs under the `subject` heading; `button` is the label of the
    link button ("Open" when not given)."""
    language = language or get_language()
    if link and not link.startswith(("https://", "http://")):
        link = None
    blocks: list[str] = []
    for paragraph in text.strip().split("\n\n"):
        lines: list[str] = []
        for line in [*paragraph.split("\n"), None]:
            if line is not None and line != link:
                lines.append(escape(line))
                continue
            if lines:
                blocks.append(PARAGRAPH.format("<br>".join(lines)))
                lines = []
            if line is not None:
                blocks.append(
                    BUTTON.substitute(
                        link=escape(link),
                        label=escape(button or translate("mail.open", language)),
                        fallback=escape(translate("mail.link_fallback", language)),
                    )
                )
    # Imported here: app.settings lists the mail settings of this package
    from app.settings import SiteSettings

    site = settings.get(SiteSettings).name
    return LAYOUT.substitute(
        language=escape(language),
        subject=escape(subject),
        site=escape(site),
        content="\n".join(blocks),
        footer=escape(translate("mail.footer", language, site=site)),
    )
