"""Email notification: send daily digest after pipeline completes."""

import logging
import smtplib
import ssl
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
from jinja2 import Environment, FileSystemLoader

from ttsfeed.analyze import EnrichResult
from ttsfeed.config import GMAIL_APP_PASSWORD, RECEIVER_EMAIL, SENDER_GMAIL

logger = logging.getLogger(__name__)

_TEMPLATES_DIR = Path(__file__).parent / "templates"
_ET = ZoneInfo("America/New_York")


def _to_et_display(created_at: str) -> str:
    """Convert UTC ISO timestamp to Eastern Time display string like 'Feb 21, 2026, 9:32 AM'."""
    dt = datetime.fromisoformat(created_at).astimezone(_ET)
    hour = dt.hour % 12 or 12
    ampm = "AM" if dt.hour < 12 else "PM"
    return f"{dt.strftime('%b')} {dt.day}, {dt.year}, {hour}:{dt.strftime('%M')} {ampm}"


def send_notification(
    reference_time: pd.Timestamp,
    new_posts: list[dict],
    enrichment: EnrichResult | None,
) -> bool:
    """Send daily digest email after pipeline completion.

    Skips silently if SENDER_GMAIL, GMAIL_APP_PASSWORD, or RECEIVER_EMAIL are not set.
    Catches and logs all exceptions to avoid failing the pipeline.

    Returns:
        True if the email was sent successfully or skipped intentionally (no credentials).
        False if credentials are present but the send attempt raised an exception.
    """
    if not (SENDER_GMAIL and GMAIL_APP_PASSWORD and RECEIVER_EMAIL):
        logger.info("Email notification skipped (SENDER_GMAIL/GMAIL_APP_PASSWORD/RECEIVER_EMAIL not set)")
        return True

    date_str = reference_time.date().isoformat()
    post_count = len(new_posts)

    subject = f"Trump Truth Social \u2014 {date_str} ({post_count} new posts)"
    ctx = _build_template_context(date_str, new_posts, enrichment)
    text_body = _render_text(ctx)
    html_body = _render_html(ctx)

    msg = MIMEMultipart("alternative")
    msg["From"] = SENDER_GMAIL
    msg["To"] = RECEIVER_EMAIL
    msg["Subject"] = subject
    msg.attach(MIMEText(text_body, "plain"))
    msg.attach(MIMEText(html_body, "html"))

    try:
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as server:
            server.login(SENDER_GMAIL, GMAIL_APP_PASSWORD)
            server.send_message(msg)
        logger.info("Notification email sent to %s", RECEIVER_EMAIL)
        return True
    except Exception:
        logger.warning("Failed to send notification email", exc_info=True)
        return False


def _build_template_context(
    date_str: str,
    new_posts: list[dict],
    enrichment: EnrichResult | None,
) -> dict:
    """Assemble the context dict passed to both Jinja2 templates."""
    sorted_posts = sorted(new_posts, key=lambda p: p.get("created_at", ""), reverse=True)
    enriched_posts = [
        {
            **post,
            "categories": (
                enrichment.post_categories.get(post.get("id", ""), [])
                if enrichment is not None
                else []
            ),
            "created_at_et": _to_et_display(post.get("created_at", "")),
        }
        for post in sorted_posts
    ]

    return {
        "date": date_str,
        "subscriber_name": None,
        "unsubscribe_url": "",
        "data": {
            "summary": {
                "new_posts_count": len(new_posts),
                "daily_summary": (
                    enrichment.daily_summary
                    if enrichment is not None
                    else "Enrichment not available."
                ),
            },
            "new_posts": enriched_posts,
        },
    }


def _render_text(ctx: dict) -> str:
    """Render the plain-text template with the given context."""
    env = Environment(loader=FileSystemLoader(_TEMPLATES_DIR), autoescape=False)
    return env.get_template("digest.txt.jinja2").render(**ctx)


def _render_html(ctx: dict) -> str:
    """Render the HTML template with the given context."""
    env = Environment(loader=FileSystemLoader(_TEMPLATES_DIR), autoescape=True)
    return env.get_template("digest.html.jinja2").render(**ctx)
