"""Tests for ttsfeed.diff — snapshot comparison and diff output."""

import json
from datetime import date

import pandas as pd

import ttsfeed.config as config_mod
import ttsfeed.diff as diff_mod
from ttsfeed.diff import _post_to_dict, find_new_posts, run_diff, save_diff

TODAY = date(2025, 1, 15)
YESTERDAY = date(2025, 1, 14)


def _patch_dirs(monkeypatch, tmp_path):
    """Redirect SNAPSHOTS_DIR and DIFFS_DIR to tmp_path."""
    monkeypatch.setattr(config_mod, "SNAPSHOTS_DIR", tmp_path)
    monkeypatch.setattr(config_mod, "DIFFS_DIR", tmp_path)
    monkeypatch.setattr(diff_mod, "DIFFS_DIR", tmp_path)


# --- find_new_posts ---


def test_find_new_posts_returns_only_new(sample_df, sample_df_yesterday):
    new = find_new_posts(sample_df, sample_df_yesterday)
    assert set(new["id"]) == {"200", "300"}


def test_find_new_posts_empty_when_identical(sample_df):
    new = find_new_posts(sample_df, sample_df)
    assert len(new) == 0


def test_find_new_posts_all_new_when_yesterday_empty(sample_df):
    empty = pd.DataFrame({"id": pd.Series([], dtype=str)})
    new = find_new_posts(sample_df, empty)
    assert len(new) == len(sample_df)


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


# --- save_diff ---


def test_save_diff_creates_json(tmp_path, monkeypatch, sample_df, sample_df_yesterday):
    _patch_dirs(monkeypatch, tmp_path)

    new_posts = find_new_posts(sample_df, sample_df_yesterday)
    save_diff(new_posts, TODAY, YESTERDAY, total_today=3, total_yesterday=1)

    data = json.loads((tmp_path / "2025-01-15.json").read_text())
    assert data["date_from"] == "2025-01-14"
    assert data["date_to"] == "2025-01-15"
    assert data["summary"]["new_posts_count"] == 2
    assert len(data["new_posts"]) == 2


def test_save_diff_zero_new_posts(tmp_path, monkeypatch, sample_df):
    _patch_dirs(monkeypatch, tmp_path)

    empty = sample_df.iloc[0:0]
    save_diff(empty, TODAY, YESTERDAY, total_today=5, total_yesterday=5)

    data = json.loads((tmp_path / "2025-01-15.json").read_text())
    assert data["summary"]["new_posts_count"] == 0
    assert data["new_posts"] == []


# --- run_diff ---


def test_run_diff_missing_today_returns_zero(tmp_path, monkeypatch):
    _patch_dirs(monkeypatch, tmp_path)
    assert run_diff(TODAY, YESTERDAY) == 0


def test_run_diff_missing_yesterday_falls_back_to_latest(tmp_path, monkeypatch, sample_df, sample_df_yesterday):
    _patch_dirs(monkeypatch, tmp_path)
    sample_df.to_parquet(tmp_path / "2025-01-15.parquet", index=False)
    # No dated yesterday file, but latest.parquet exists
    sample_df_yesterday.to_parquet(tmp_path / "latest.parquet", index=False)

    count = run_diff(TODAY, YESTERDAY)
    assert count == 2  # 3 today - 1 in latest


def test_run_diff_missing_yesterday_no_latest_returns_zero(tmp_path, monkeypatch, sample_df):
    _patch_dirs(monkeypatch, tmp_path)
    sample_df.to_parquet(tmp_path / "2025-01-15.parquet", index=False)
    assert run_diff(TODAY, YESTERDAY) == 0


def test_run_diff_end_to_end(tmp_path, monkeypatch, sample_df, sample_df_yesterday):
    _patch_dirs(monkeypatch, tmp_path)

    sample_df.to_parquet(tmp_path / "2025-01-15.parquet", index=False)
    sample_df_yesterday.to_parquet(tmp_path / "2025-01-14.parquet", index=False)

    count = run_diff(TODAY, YESTERDAY)
    assert count == 2

    data = json.loads((tmp_path / "2025-01-15.json").read_text())
    assert data["summary"]["new_posts_count"] == 2
