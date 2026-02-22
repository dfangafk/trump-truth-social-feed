"""Email notification: send daily digest after pipeline completes."""

import logging
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import pandas as pd

from ttsenrich.analyze import EnrichResult
from ttsenrich.config import GMAIL_APP_PASS, GMAIL_USER, NOTIFY_EMAIL

logger = logging.getLogger(__name__)


def send_notification(
    reference_time: pd.Timestamp,
    new_posts: list[dict],
    enrichment: EnrichResult | None,
) -> None:
    """Send daily digest email after pipeline completion.

    Skips silently if GMAIL_USER, GMAIL_APP_PASS, or NOTIFY_EMAIL are not set.
    Catches and logs all exceptions to avoid failing the pipeline.
    """
    if not (GMAIL_USER and GMAIL_APP_PASS and NOTIFY_EMAIL):
        logger.info("Email notification skipped (GMAIL_USER/GMAIL_APP_PASS/NOTIFY_EMAIL not set)")
        return

    date_str = reference_time.date().isoformat()
    post_count = len(new_posts)

    subject = f"Trump Truth Social \u2014 {date_str} ({post_count} new posts)"
    body = _build_body(date_str, new_posts, enrichment)

    msg = MIMEMultipart()
    msg["From"] = GMAIL_USER
    msg["To"] = NOTIFY_EMAIL
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    try:
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as server:
            server.login(GMAIL_USER, GMAIL_APP_PASS)
            server.send_message(msg)
        logger.info("Notification email sent to %s", NOTIFY_EMAIL)
    except Exception:
        logger.warning("Failed to send notification email", exc_info=True)


def _build_body(
    date_str: str,
    new_posts: list[dict],
    enrichment: EnrichResult | None,
) -> str:
    """Build plain-text email body."""
    lines: list[str] = [
        f"Date: {date_str}",
        f"New posts: {len(new_posts)}",
        "",
        "--- Summary ---",
        enrichment.daily_summary if enrichment is not None else "Enrichment not available.",
        "",
        "--- Posts ---",
    ]

    for i, post in enumerate(new_posts, 1):
        created_at = _format_timestamp(post.get("created_at", ""))
        content = post.get("content", "")
        url = post.get("url", "")
        categories = (
            enrichment.post_categories.get(post.get("id", ""), [])
            if enrichment is not None
            else []
        )

        lines.append(f"[{i}] {created_at}")
        lines.append(f"    {content}")
        if categories:
            lines.append(f"    Categories: {', '.join(categories)}")
        lines.append(f"    URL: {url}")
        lines.append("")

    return "\n".join(lines)


def _format_timestamp(ts: str) -> str:
    """Parse and reformat a timestamp string to 'YYYY-MM-DD HH:MM UTC'."""
    try:
        t = pd.Timestamp(ts)
        if t.tzinfo is None:
            t = t.tz_localize("UTC")
        else:
            t = t.tz_convert("UTC")
        return t.strftime("%Y-%m-%d %H:%M UTC")
    except Exception:
        return ts
