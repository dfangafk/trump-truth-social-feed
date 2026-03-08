"""Email notification: send daily digest after pipeline completes."""

import functools
import logging
import smtplib
import ssl
from collections.abc import Callable
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from zoneinfo import ZoneInfo

import pandas as pd
from jinja2 import Environment, FileSystemLoader

from ttsfeed.analyze import EnrichResult
from ttsfeed.config import settings

NotifyFn = Callable[[pd.Timestamp, list[dict], "EnrichResult | None"], None]

logger = logging.getLogger(__name__)


def _media_type(url: str) -> str:
    """Return 'video' for .mp4 URLs, 'image' for everything else."""
    return "video" if url.lower().endswith(".mp4") else "image"


def _to_et_display(created_at: str) -> str:
    """Convert UTC ISO timestamp to display timezone string like 'Feb 21, 2026, 9:32 AM'."""
    tz = ZoneInfo(settings.notify.timezone)
    dt = datetime.fromisoformat(created_at).astimezone(tz)
    return f"{dt.strftime('%b')} {dt.day}, {dt.year}, {dt.hour % 12 or 12}:{dt.strftime('%M')} {'AM' if dt.hour < 12 else 'PM'}"


@functools.lru_cache(maxsize=2)
def _get_jinja_env(templates_dir: str, autoescape: bool) -> Environment:
    """Return a cached Jinja2 Environment for the given directory and autoescape mode."""
    return Environment(loader=FileSystemLoader(templates_dir), autoescape=autoescape)


def send_notification(
    reference_time: pd.Timestamp,
    new_posts: list[dict],
    enrichment: EnrichResult | None,
) -> None:
    """Send daily digest email after pipeline completion.

    Skips silently if SENDER_GMAIL, GMAIL_APP_PASSWORD, or RECEIVER_EMAIL are not set.
    Catches and logs all exceptions to avoid failing the pipeline.
    """
    if not (settings.sender_gmail and settings.gmail_app_password and settings.receiver_email):
        logger.info("Email notification skipped (sender_gmail/gmail_app_password/receiver_email not set)")
        return

    tz = ZoneInfo(settings.notify.timezone)
    date_str = reference_time.astimezone(tz).date().isoformat()
    post_count = len(new_posts)

    subject = settings.notify.subject_template.format(date=date_str, count=post_count)
    ctx = build_template_context(date_str, new_posts, enrichment)
    text_body = render_text(ctx)
    html_body = render_html(ctx)

    msg = MIMEMultipart("alternative")
    msg["From"] = settings.sender_gmail
    msg["To"] = settings.receiver_email
    msg["Subject"] = subject
    msg.attach(MIMEText(text_body, "plain"))
    msg.attach(MIMEText(html_body, "html"))

    try:
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(settings.notify.smtp_host, settings.notify.smtp_port, context=context) as server:
            server.login(settings.sender_gmail, settings.gmail_app_password)
            server.send_message(msg)
        _email = settings.receiver_email
        _masked = _email[:2] + "***" + _email[_email.index("@"):]
        logger.info("Notification email sent to %s", _masked)
    except Exception:
        logger.warning("Failed to send notification email", exc_info=True)


def build_template_context(
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
            "media_items": [{"url": u, "type": _media_type(u)} for u in post.get("media", [])],
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


def render_text(ctx: dict) -> str:
    """Render the plain-text template with the given context."""
    env = _get_jinja_env(str(settings.paths.templates_dir), autoescape=False)
    return env.get_template("digest.txt.jinja2").render(**ctx)


def render_html(ctx: dict) -> str:
    """Render the HTML template with the given context."""
    env = _get_jinja_env(str(settings.paths.templates_dir), autoescape=True)
    return env.get_template("digest.html.jinja2").render(**ctx)
