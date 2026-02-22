"""Tests for ttsfeed.fetch — download, parse, and filter."""

import io

import pandas as pd
import pytest
import requests as req_lib

from ttsfeed.fetch import bytes_to_dataframe, download_archive, filter_recent_posts


# --- download_archive ---


def test_download_archive_failure_raises(mocker):
    mocker.patch(
        "ttsfeed.fetch.requests.get",
        side_effect=req_lib.RequestException("fail"),
    )
    with pytest.raises(req_lib.RequestException):
        download_archive()


# --- bytes_to_dataframe ---


def test_bytes_to_dataframe_json(json_bytes):
    df = bytes_to_dataframe(json_bytes)
    assert isinstance(df, pd.DataFrame)
    assert pd.api.types.is_string_dtype(df["id"])


def test_bytes_to_dataframe_id_normalized_to_string():
    df_int = pd.DataFrame({"id": [300, 100, 200], "content": ["c", "a", "b"]})
    raw = df_int.to_json(orient="records").encode()

    result = bytes_to_dataframe(raw)
    assert pd.api.types.is_string_dtype(result["id"])
    assert result["id"].tolist() == ["100", "200", "300"]


def test_bytes_to_dataframe_sorted_by_id():
    df = pd.DataFrame({"id": ["300", "100", "200"]})
    raw = df.to_json(orient="records").encode()

    result = bytes_to_dataframe(raw)
    assert result["id"].tolist() == ["100", "200", "300"]


# --- filter_recent_posts ---


REF_TIME = pd.Timestamp("2025-06-15T12:00:00Z")


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
