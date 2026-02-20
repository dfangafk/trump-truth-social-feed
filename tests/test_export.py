"""Tests for ttsfeed.export — post serialization and JSON output."""

import json

import pandas as pd

import ttsfeed.config as config_mod
import ttsfeed.export as export_mod
from ttsfeed.export import _post_to_dict, save_output

# Fixed reference time for deterministic tests
REF_TIME = pd.Timestamp("2025-06-15T12:00:00Z")


def _patch_dirs(monkeypatch, tmp_path):
    """Redirect OUTPUT_DIR to tmp_path."""
    monkeypatch.setattr(config_mod, "OUTPUT_DIR", tmp_path)
    monkeypatch.setattr(export_mod, "OUTPUT_DIR", tmp_path)


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
