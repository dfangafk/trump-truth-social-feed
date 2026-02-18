"""Tests for ttsfeed.filter — created_at filtering and JSON output."""

import json

import pandas as pd

import ttsfeed.config as config_mod
import ttsfeed.filter as filter_mod
from ttsfeed.filter import _post_to_dict, filter_recent_posts, save_output

# Fixed reference time for deterministic tests
REF_TIME = pd.Timestamp("2025-06-15T12:00:00Z")


def _patch_dirs(monkeypatch, tmp_path):
    """Redirect OUTPUT_DIR to tmp_path."""
    monkeypatch.setattr(config_mod, "OUTPUT_DIR", tmp_path)
    monkeypatch.setattr(filter_mod, "OUTPUT_DIR", tmp_path)


# --- filter_recent_posts ---


def test_filter_recent_posts_returns_recent():
    """Posts within the window are returned."""
    df = pd.DataFrame({
        "id": ["1", "2", "3"],
        "created_at": [
            (REF_TIME - pd.Timedelta(hours=48)).isoformat(),
            (REF_TIME - pd.Timedelta(hours=12)).isoformat(),
            (REF_TIME - pd.Timedelta(hours=1)).isoformat(),
        ],
    })
    result = filter_recent_posts(df, hours=24, reference_time=REF_TIME)
    assert set(result["id"]) == {"2", "3"}


def test_filter_recent_posts_none_recent():
    """All posts older than window returns empty."""
    old = (REF_TIME - pd.Timedelta(hours=48)).isoformat()
    df = pd.DataFrame({
        "id": ["1", "2"],
        "created_at": [old, old],
    })
    result = filter_recent_posts(df, hours=24, reference_time=REF_TIME)
    assert len(result) == 0


def test_filter_recent_posts_all_recent():
    """All posts within window are returned."""
    recent = (REF_TIME - pd.Timedelta(hours=1)).isoformat()
    df = pd.DataFrame({
        "id": ["1", "2"],
        "created_at": [recent, recent],
    })
    result = filter_recent_posts(df, hours=24, reference_time=REF_TIME)
    assert len(result) == 2


def test_filter_recent_posts_custom_window():
    """Custom hour window works."""
    df = pd.DataFrame({
        "id": ["1", "2"],
        "created_at": [
            (REF_TIME - pd.Timedelta(hours=5)).isoformat(),
            (REF_TIME - pd.Timedelta(hours=1)).isoformat(),
        ],
    })
    result = filter_recent_posts(df, hours=2, reference_time=REF_TIME)
    assert set(result["id"]) == {"2"}


def test_filter_recent_posts_defaults_to_now():
    """Without reference_time, uses current time."""
    now = pd.Timestamp.now("UTC")
    recent = (now - pd.Timedelta(hours=1)).isoformat()
    df = pd.DataFrame({
        "id": ["1"],
        "created_at": [recent],
    })
    result = filter_recent_posts(df, hours=24)
    assert len(result) == 1


# --- _post_to_dict ---


def test_post_to_dict_basic_fields(sample_df):
    result = _post_to_dict(sample_df.iloc[0])
    assert result["id"] == "100"
    assert isinstance(result["content"], str)
    assert isinstance(result["media"], list)
    assert isinstance(result["replies_count"], int)


def test_post_to_dict_with_list_media():
    row = pd.Series({
        "id": "42", "created_at": "t", "content": "c",
        "url": "https://example.com",
        "media_attachments": [{"url": "https://img.example.com/photo.jpg"}],
        "replies_count": 0, "reblogs_count": 0, "favourites_count": 0,
    })
    result = _post_to_dict(row)
    assert result["media"] == [{"url": "https://img.example.com/photo.jpg"}]


def test_post_to_dict_with_json_string_media():
    row = pd.Series({
        "id": "42", "created_at": "t", "content": "c",
        "url": "https://example.com",
        "media_attachments": '[{"url": "https://img.example.com/photo.jpg"}]',
        "replies_count": 0, "reblogs_count": 0, "favourites_count": 0,
    })
    result = _post_to_dict(row)
    assert isinstance(result["media"], list)
    assert result["media"][0]["url"] == "https://img.example.com/photo.jpg"


def test_post_to_dict_nan_counts():
    row = pd.Series({
        "id": "42", "created_at": "t", "content": "c", "url": "u",
        "media_attachments": None,
        "replies_count": float("nan"), "reblogs_count": None, "favourites_count": 0,
    })
    result = _post_to_dict(row)
    assert result["replies_count"] == 0
    assert result["reblogs_count"] == 0
    assert result["favourites_count"] == 0


def test_post_to_dict_none_media():
    row = pd.Series({
        "id": "42", "created_at": "t", "content": "c", "url": "u",
        "media_attachments": None,
        "replies_count": 0, "reblogs_count": 0, "favourites_count": 0,
    })
    assert _post_to_dict(row)["media"] == []


# --- save_output ---


def test_save_output_creates_json(tmp_path, monkeypatch, sample_df):
    _patch_dirs(monkeypatch, tmp_path)

    new_posts = sample_df.iloc[1:]  # 2 "new" posts
    save_output(new_posts, total_archive=3, hours=24, reference_time=REF_TIME)

    today_str = REF_TIME.date().isoformat()
    data = json.loads((tmp_path / f"{today_str}.json").read_text())
    assert data["as_of"] == REF_TIME.isoformat()
    assert data["window_hours"] == 24
    assert data["summary"]["total_posts_in_archive"] == 3
    assert data["summary"]["new_posts_count"] == 2
    assert len(data["new_posts"]) == 2


def test_save_output_zero_new_posts(tmp_path, monkeypatch, sample_df):
    _patch_dirs(monkeypatch, tmp_path)

    empty = sample_df.iloc[0:0]
    save_output(empty, total_archive=5, hours=24, reference_time=REF_TIME)

    today_str = REF_TIME.date().isoformat()
    data = json.loads((tmp_path / f"{today_str}.json").read_text())
    assert data["summary"]["new_posts_count"] == 0
    assert data["new_posts"] == []
