"""Tests for ttsfeed.export — post serialization and JSON output."""

import json

import pandas as pd

from ttsfeed.analyze import EnrichResult
from ttsfeed.config import settings
from ttsfeed.export import post_to_dict, save_output

# Fixed reference time for deterministic tests
REF_TIME = pd.Timestamp("2025-06-15T12:00:00Z")


# --- post_to_dict ---


def testpost_to_dict_basic_fields(sample_df):
    result = post_to_dict(sample_df.iloc[0])
    assert result["id"] == "100"
    assert isinstance(result["content"], str)
    assert isinstance(result["media"], list)
    assert isinstance(result["replies_count"], int)


def testpost_to_dict_with_flat_url_media():
    """media column (flat list of URL strings) is passed through directly."""
    row = pd.Series({
        "id": "42", "created_at": "t", "content": "c",
        "url": "https://example.com",
        "media": ["https://example.com/video.mp4"],
        "replies_count": 0, "reblogs_count": 0, "favourites_count": 0,
    })
    result = post_to_dict(row)
    assert result["media"] == ["https://example.com/video.mp4"]


def testpost_to_dict_nan_counts():
    row = pd.Series({
        "id": "42", "created_at": "t", "content": "c", "url": "u",
        "media": None,
        "replies_count": float("nan"), "reblogs_count": None, "favourites_count": 0,
    })
    result = post_to_dict(row)
    assert result["replies_count"] == 0
    assert result["reblogs_count"] == 0
    assert result["favourites_count"] == 0


def testpost_to_dict_none_media():
    row = pd.Series({
        "id": "42", "created_at": "t", "content": "c", "url": "u",
        "media": None,
        "replies_count": 0, "reblogs_count": 0, "favourites_count": 0,
    })
    assert post_to_dict(row)["media"] == []


# --- save_output ---


def _posts_from_df(df: pd.DataFrame) -> list[dict]:
    """Convert a DataFrame to a list of post dicts for save_output."""
    return [post_to_dict(row) for _, row in df.iterrows()]


def test_save_output_creates_json(tmp_path, monkeypatch, sample_df):
    monkeypatch.setattr(settings.paths, "enriched_output_dir", tmp_path)

    new_posts = _posts_from_df(sample_df.iloc[1:])  # 2 "new" posts
    save_output(new_posts, total_archive=3, hours=24, reference_time=REF_TIME)

    today_str = REF_TIME.date().isoformat()
    data = json.loads((tmp_path / f"{today_str}.json").read_text())
    assert data["as_of"] == REF_TIME.isoformat()
    assert data["window_hours"] == 24
    assert data["summary"]["total_posts_in_archive"] == 3
    assert data["summary"]["new_posts_count"] == 2
    assert len(data["new_posts"]) == 2


def test_save_output_zero_new_posts(tmp_path, monkeypatch, sample_df):
    monkeypatch.setattr(settings.paths, "enriched_output_dir", tmp_path)

    save_output([], total_archive=5, hours=24, reference_time=REF_TIME)

    today_str = REF_TIME.date().isoformat()
    data = json.loads((tmp_path / f"{today_str}.json").read_text())
    assert data["summary"]["new_posts_count"] == 0
    assert data["new_posts"] == []


def test_save_output_with_enrichment_embeds_per_post_categories(
    tmp_path, monkeypatch, sample_df
):
    monkeypatch.setattr(settings.paths, "enriched_output_dir", tmp_path)

    new_posts = _posts_from_df(sample_df.iloc[1:])
    enrichment = EnrichResult(
        daily_summary="Summary text",
        post_categories={"200": ["immigration"], "300": ["economy / trade"]},
    )
    save_output(
        new_posts,
        total_archive=3,
        hours=24,
        reference_time=REF_TIME,
        enrichment=enrichment,
    )

    today_str = REF_TIME.date().isoformat()
    data = json.loads((tmp_path / f"{today_str}.json").read_text())
    assert data["summary"]["daily_summary"] == "Summary text"
    assert "categories" not in data["summary"]
    posts_by_id = {post["id"]: post for post in data["new_posts"]}
    assert posts_by_id["200"]["categories"] == ["immigration"]
    assert posts_by_id["300"]["categories"] == ["economy / trade"]


def test_save_output_without_enrichment_posts_have_no_categories(
    tmp_path, monkeypatch, sample_df
):
    monkeypatch.setattr(settings.paths, "enriched_output_dir", tmp_path)

    new_posts = _posts_from_df(sample_df.iloc[1:])
    save_output(new_posts, total_archive=3, hours=24, reference_time=REF_TIME)

    today_str = REF_TIME.date().isoformat()
    data = json.loads((tmp_path / f"{today_str}.json").read_text())
    assert all("categories" not in post for post in data["new_posts"])


def test_save_output_with_explicit_output_name(tmp_path, monkeypatch, sample_df):
    monkeypatch.setattr(settings.paths, "enriched_output_dir", tmp_path)

    new_posts = _posts_from_df(sample_df.iloc[1:])
    save_output(
        new_posts,
        total_archive=3,
        hours=24,
        reference_time=REF_TIME,
        output_path=tmp_path / "raw.json",
    )

    assert (tmp_path / "raw.json").exists()
