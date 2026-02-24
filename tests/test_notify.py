"""Tests for ttsfeed.notify — email notification."""

import pandas as pd
import pytest

from ttsfeed.analyze import EnrichResult
from ttsfeed.notify import _build_template_context, _media_type, _render_text, _to_et_display, send_notification


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
    mocker.patch("ttsfeed.notify.SENDER_GMAIL", "")
    mocker.patch("ttsfeed.notify.GMAIL_APP_PASSWORD", "")
    mocker.patch("ttsfeed.notify.RECEIVER_EMAIL", "")
    mock_smtp = mocker.patch("ttsfeed.notify.smtplib.SMTP_SSL")

    send_notification(REFERENCE_TIME, SAMPLE_POSTS, None)

    mock_smtp.assert_not_called()


def test_send_notification_skips_when_partial_creds(mocker):
    """Should skip if only some credentials are set."""
    mocker.patch("ttsfeed.notify.SENDER_GMAIL", "sender@gmail.com")
    mocker.patch("ttsfeed.notify.GMAIL_APP_PASSWORD", "")
    mocker.patch("ttsfeed.notify.RECEIVER_EMAIL", "recipient@example.com")
    mock_smtp = mocker.patch("ttsfeed.notify.smtplib.SMTP_SSL")

    send_notification(REFERENCE_TIME, SAMPLE_POSTS, None)

    mock_smtp.assert_not_called()


def test_send_notification_calls_smtp(mocker):
    """Should connect and send when all credentials are set."""
    mocker.patch("ttsfeed.notify.SENDER_GMAIL", "sender@gmail.com")
    mocker.patch("ttsfeed.notify.GMAIL_APP_PASSWORD", "abcdabcdabcdabcd")
    mocker.patch("ttsfeed.notify.RECEIVER_EMAIL", "recipient@example.com")

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
    mocker.patch("ttsfeed.notify.SENDER_GMAIL", "sender@gmail.com")
    mocker.patch("ttsfeed.notify.GMAIL_APP_PASSWORD", "abcdabcdabcdabcd")
    mocker.patch("ttsfeed.notify.RECEIVER_EMAIL", "recipient@example.com")

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
    mocker.patch("ttsfeed.notify.SENDER_GMAIL", "sender@gmail.com")
    mocker.patch("ttsfeed.notify.GMAIL_APP_PASSWORD", "abcdabcdabcdabcd")
    mocker.patch("ttsfeed.notify.RECEIVER_EMAIL", "recipient@example.com")

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
    mocker.patch("ttsfeed.notify.SENDER_GMAIL", "sender@gmail.com")
    mocker.patch("ttsfeed.notify.GMAIL_APP_PASSWORD", "abcdabcdabcdabcd")
    mocker.patch("ttsfeed.notify.RECEIVER_EMAIL", "recipient@example.com")
    mocker.patch("ttsfeed.notify.smtplib.SMTP_SSL", side_effect=OSError("connection refused"))

    # Should not raise
    send_notification(REFERENCE_TIME, SAMPLE_POSTS, None)


def test_template_context_no_enrichment():
    """Context without enrichment has 'Enrichment not available.' and empty categories."""
    ctx = _build_template_context("2026-02-21", SAMPLE_POSTS, None)
    assert ctx["data"]["summary"]["daily_summary"] == "Enrichment not available."
    assert all(p["categories"] == [] for p in ctx["data"]["new_posts"])
    contents = [p["content"] for p in ctx["data"]["new_posts"]]
    assert "First post content" in contents
    assert "Second post content" in contents


def test_template_context_with_enrichment():
    """Context with enrichment populates summary and per-post categories."""
    ctx = _build_template_context("2026-02-21", SAMPLE_POSTS, SAMPLE_ENRICHMENT)
    assert ctx["data"]["summary"]["daily_summary"] == "Trump posted about trade and immigration."
    cats_by_id = {p["id"]: p["categories"] for p in ctx["data"]["new_posts"]}
    assert cats_by_id["1"] == ["economy / trade"]
    assert cats_by_id["2"] == ["immigration"]


def test_to_et_display_formats_correctly():
    """UTC timestamp is converted to Eastern Time and formatted like Truth Social."""
    # 2026-02-21T14:32:00Z = 9:32 AM EST (UTC-5)
    assert _to_et_display("2026-02-21T14:32:00Z") == "Feb 21, 2026, 9:32 AM"
    # 2026-02-21T12:00:00Z = 7:00 AM EST
    assert _to_et_display("2026-02-21T12:00:00Z") == "Feb 21, 2026, 7:00 AM"
    # Midnight UTC = 7:00 PM previous day EST
    assert _to_et_display("2026-02-22T00:00:00Z") == "Feb 21, 2026, 7:00 PM"


def test_template_context_includes_created_at_et():
    """Each post in context should have a created_at_et field."""
    ctx = _build_template_context("2026-02-21", SAMPLE_POSTS, None)
    for post in ctx["data"]["new_posts"]:
        assert "created_at_et" in post
        assert "AM" in post["created_at_et"] or "PM" in post["created_at_et"]


def test_rendered_text_contains_urls():
    """Rendered plain-text body includes URLs for each post."""
    ctx = _build_template_context("2026-02-21", SAMPLE_POSTS, None)
    body = _render_text(ctx)
    assert "https://truthsocial.com/@realDonaldTrump/1" in body
    assert "https://truthsocial.com/@realDonaldTrump/2" in body


def test_media_type_classifies_mp4_as_video():
    assert _media_type("https://example.com/foo.mp4") == "video"


def test_media_type_classifies_jpg_as_image():
    assert _media_type("https://example.com/foo.jpg") == "image"


def test_build_template_context_populates_media_items():
    """Posts with media list get a media_items list with correct type/url dicts."""
    posts = [
        {
            "id": "99",
            "created_at": "2026-02-21T14:00:00Z",
            "content": "post with media",
            "url": "https://truthsocial.com/@realDonaldTrump/99",
            "media": ["https://cdn.example.com/a.jpg", "https://cdn.example.com/b.mp4"],
        }
    ]
    ctx = _build_template_context("2026-02-21", posts, None)
    post = ctx["data"]["new_posts"][0]
    assert post["media_items"] == [
        {"url": "https://cdn.example.com/a.jpg", "type": "image"},
        {"url": "https://cdn.example.com/b.mp4", "type": "video"},
    ]
