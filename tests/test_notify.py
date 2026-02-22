"""Tests for ttsfeed.notify — email notification."""

import pandas as pd
import pytest

from ttsfeed.analyze import EnrichResult
from ttsfeed.notify import _build_body, send_notification


REFERENCE_TIME = pd.Timestamp("2026-02-21T14:00:00Z")

SAMPLE_POSTS = [
    {
        "id": "1",
        "created_at": "2026-02-21T14:32:00Z",
        "content": "First post content",
        "url": "https://truthsocial.com/@realDonaldTrump/1",
    },
    {
        "id": "2",
        "created_at": "2026-02-21T12:00:00Z",
        "content": "Second post content",
        "url": "https://truthsocial.com/@realDonaldTrump/2",
    },
]

SAMPLE_ENRICHMENT = EnrichResult(
    daily_summary="Trump posted about trade and immigration.",
    post_categories={"1": ["economy / trade"], "2": ["immigration"]},
)


def test_send_notification_skips_when_no_creds(mocker):
    """Should log and return early when any credential is missing."""
    mocker.patch("ttsfeed.notify.GMAIL_USER", "")
    mocker.patch("ttsfeed.notify.GMAIL_APP_PASS", "")
    mocker.patch("ttsfeed.notify.NOTIFY_EMAIL", "")
    mock_smtp = mocker.patch("ttsfeed.notify.smtplib.SMTP_SSL")

    send_notification(REFERENCE_TIME, SAMPLE_POSTS, None)

    mock_smtp.assert_not_called()


def test_send_notification_skips_when_partial_creds(mocker):
    """Should skip if only some credentials are set."""
    mocker.patch("ttsfeed.notify.GMAIL_USER", "sender@gmail.com")
    mocker.patch("ttsfeed.notify.GMAIL_APP_PASS", "")
    mocker.patch("ttsfeed.notify.NOTIFY_EMAIL", "recipient@example.com")
    mock_smtp = mocker.patch("ttsfeed.notify.smtplib.SMTP_SSL")

    send_notification(REFERENCE_TIME, SAMPLE_POSTS, None)

    mock_smtp.assert_not_called()


def test_send_notification_calls_smtp(mocker):
    """Should connect and send when all credentials are set."""
    mocker.patch("ttsfeed.notify.GMAIL_USER", "sender@gmail.com")
    mocker.patch("ttsfeed.notify.GMAIL_APP_PASS", "abcdabcdabcdabcd")
    mocker.patch("ttsfeed.notify.NOTIFY_EMAIL", "recipient@example.com")

    mock_server = mocker.MagicMock()
    mock_smtp_cls = mocker.patch("ttsfeed.notify.smtplib.SMTP_SSL")
    mock_smtp_cls.return_value.__enter__ = mocker.Mock(return_value=mock_server)
    mock_smtp_cls.return_value.__exit__ = mocker.Mock(return_value=False)

    send_notification(REFERENCE_TIME, SAMPLE_POSTS, SAMPLE_ENRICHMENT)

    mock_smtp_cls.assert_called_once_with("smtp.gmail.com", 465, context=mocker.ANY)
    mock_server.login.assert_called_once_with("sender@gmail.com", "abcdabcdabcdabcd")
    mock_server.send_message.assert_called_once()


def test_send_notification_subject_contains_date_and_count(mocker):
    """Subject should contain the date and post count."""
    mocker.patch("ttsfeed.notify.GMAIL_USER", "sender@gmail.com")
    mocker.patch("ttsfeed.notify.GMAIL_APP_PASS", "abcdabcdabcdabcd")
    mocker.patch("ttsfeed.notify.NOTIFY_EMAIL", "recipient@example.com")

    mock_server = mocker.MagicMock()
    mock_smtp_cls = mocker.patch("ttsfeed.notify.smtplib.SMTP_SSL")
    mock_smtp_cls.return_value.__enter__ = mocker.Mock(return_value=mock_server)
    mock_smtp_cls.return_value.__exit__ = mocker.Mock(return_value=False)

    send_notification(REFERENCE_TIME, SAMPLE_POSTS, SAMPLE_ENRICHMENT)

    sent_msg = mock_server.send_message.call_args[0][0]
    assert "2026-02-21" in sent_msg["Subject"]
    assert "2 new posts" in sent_msg["Subject"]


def test_send_notification_body_contains_summary(mocker):
    """Body should include the daily summary when enrichment is present."""
    mocker.patch("ttsfeed.notify.GMAIL_USER", "sender@gmail.com")
    mocker.patch("ttsfeed.notify.GMAIL_APP_PASS", "abcdabcdabcdabcd")
    mocker.patch("ttsfeed.notify.NOTIFY_EMAIL", "recipient@example.com")

    mock_server = mocker.MagicMock()
    mock_smtp_cls = mocker.patch("ttsfeed.notify.smtplib.SMTP_SSL")
    mock_smtp_cls.return_value.__enter__ = mocker.Mock(return_value=mock_server)
    mock_smtp_cls.return_value.__exit__ = mocker.Mock(return_value=False)

    send_notification(REFERENCE_TIME, SAMPLE_POSTS, SAMPLE_ENRICHMENT)

    sent_msg = mock_server.send_message.call_args[0][0]
    # MIMEMultipart: first payload item is the MIMEText part
    body = sent_msg.get_payload(0).get_payload(decode=True).decode()
    assert "Trump posted about trade and immigration." in body


def test_send_notification_logs_warning_on_smtp_error(mocker):
    """SMTP failure should be caught and logged, not raised."""
    mocker.patch("ttsfeed.notify.GMAIL_USER", "sender@gmail.com")
    mocker.patch("ttsfeed.notify.GMAIL_APP_PASS", "abcdabcdabcdabcd")
    mocker.patch("ttsfeed.notify.NOTIFY_EMAIL", "recipient@example.com")
    mocker.patch("ttsfeed.notify.smtplib.SMTP_SSL", side_effect=OSError("connection refused"))

    # Should not raise
    send_notification(REFERENCE_TIME, SAMPLE_POSTS, None)


def test_build_body_no_enrichment():
    """Body without enrichment shows 'Enrichment not available.' in summary."""
    body = _build_body("2026-02-21", SAMPLE_POSTS, None)
    assert "Enrichment not available." in body
    assert "First post content" in body
    assert "Second post content" in body


def test_build_body_with_enrichment():
    """Body with enrichment shows summary and per-post categories."""
    body = _build_body("2026-02-21", SAMPLE_POSTS, SAMPLE_ENRICHMENT)
    assert "Trump posted about trade and immigration." in body
    assert "economy / trade" in body
    assert "immigration" in body
    assert "First post content" in body


def test_build_body_post_urls():
    """Body should include the URL for each post."""
    body = _build_body("2026-02-21", SAMPLE_POSTS, None)
    assert "https://truthsocial.com/@realDonaldTrump/1" in body
    assert "https://truthsocial.com/@realDonaldTrump/2" in body
