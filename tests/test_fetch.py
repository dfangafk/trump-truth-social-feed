"""Tests for ttsfeed.fetch — download, parse, and filter."""

import io
from unittest.mock import MagicMock

import pandas as pd
import pytest
import requests as req_lib

from ttsfeed.fetch import bytes_to_dataframe, download_archive, filter_recent_posts


# --- download_archive ---


def test_download_archive_parquet_success(mocker, parquet_bytes):
    mock_resp = MagicMock()
    mock_resp.content = parquet_bytes
    mock_resp.raise_for_status.return_value = None
    mocker.patch("ttsfeed.fetch.requests.get", return_value=mock_resp)

    raw, fmt = download_archive()
    assert fmt == "parquet"
    assert raw == parquet_bytes


def test_download_archive_falls_back_to_json(mocker):
    json_bytes = b'[{"id": "1"}]'
    mock_resp_json = MagicMock()
    mock_resp_json.content = json_bytes
    mock_resp_json.raise_for_status.return_value = None

    mock_get = mocker.patch("ttsfeed.fetch.requests.get")
    mock_get.side_effect = [
        req_lib.RequestException("timeout"),
        mock_resp_json,
    ]

    raw, fmt = download_archive()
    assert raw == json_bytes
    assert fmt == "json"
    assert mock_get.call_count == 2


def test_download_archive_both_fail_raises(mocker):
    mocker.patch(
        "ttsfeed.fetch.requests.get",
        side_effect=req_lib.RequestException("fail"),
    )
    with pytest.raises(req_lib.RequestException):
        download_archive()


# --- bytes_to_dataframe ---


def test_bytes_to_dataframe_parquet(parquet_bytes):
    df = bytes_to_dataframe(parquet_bytes, fmt="parquet")
    assert isinstance(df, pd.DataFrame)
    assert pd.api.types.is_string_dtype(df["id"])
    assert len(df) == 3


def test_bytes_to_dataframe_json(json_bytes):
    df = bytes_to_dataframe(json_bytes, fmt="json")
    assert isinstance(df, pd.DataFrame)
    assert pd.api.types.is_string_dtype(df["id"])


def test_bytes_to_dataframe_id_normalized_to_string():
    df_int = pd.DataFrame({"id": [300, 100, 200], "content": ["c", "a", "b"]})
    buf = io.BytesIO()
    df_int.to_parquet(buf, index=False)

    result = bytes_to_dataframe(buf.getvalue(), fmt="parquet")
    assert pd.api.types.is_string_dtype(result["id"])
    assert result["id"].tolist() == ["100", "200", "300"]


def test_bytes_to_dataframe_sorted_by_id():
    df = pd.DataFrame({"id": ["300", "100", "200"]})
    buf = io.BytesIO()
    df.to_parquet(buf, index=False)

    result = bytes_to_dataframe(buf.getvalue(), fmt="parquet")
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
