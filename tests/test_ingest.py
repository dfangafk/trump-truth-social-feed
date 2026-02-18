"""Tests for ttsfeed.ingest — download, parse, save, and cleanup."""

import io
from datetime import date, timedelta
from unittest.mock import MagicMock

import pandas as pd
import pytest
import requests as req_lib

import ttsfeed.config as config_mod
import ttsfeed.ingest as ingest_mod
from ttsfeed.ingest import (
    SNAPSHOT_RETENTION_DAYS,
    bytes_to_dataframe,
    cleanup_old_snapshots,
    download_archive,
    save_snapshot,
)


# --- download_archive ---


def test_download_archive_parquet_success(mocker, parquet_bytes):
    mock_resp = MagicMock()
    mock_resp.content = parquet_bytes
    mock_resp.raise_for_status.return_value = None
    mocker.patch("ttsfeed.ingest.requests.get", return_value=mock_resp)

    raw, fmt = download_archive()
    assert fmt == "parquet"
    assert raw == parquet_bytes


def test_download_archive_falls_back_to_json(mocker):
    json_bytes = b'[{"id": "1"}]'
    mock_resp_json = MagicMock()
    mock_resp_json.content = json_bytes
    mock_resp_json.raise_for_status.return_value = None

    mock_get = mocker.patch("ttsfeed.ingest.requests.get")
    mock_get.side_effect = [
        req_lib.RequestException("timeout"),
        mock_resp_json,
    ]

    raw, fmt = download_archive()
    assert raw == json_bytes
    assert mock_get.call_count == 2


def test_download_archive_both_fail_raises(mocker):
    mocker.patch(
        "ttsfeed.ingest.requests.get",
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


# --- save_snapshot ---


def _patch_snapshots_dir(monkeypatch, tmp_path):
    """Redirect SNAPSHOTS_DIR to tmp_path in both config and ingest modules."""
    monkeypatch.setattr(config_mod, "SNAPSHOTS_DIR", tmp_path)
    monkeypatch.setattr(ingest_mod, "SNAPSHOTS_DIR", tmp_path)


def test_save_snapshot_creates_files(tmp_path, monkeypatch, sample_df):
    _patch_snapshots_dir(monkeypatch, tmp_path)
    d = date(2025, 1, 15)
    save_snapshot(sample_df, d)

    assert (tmp_path / "2025-01-15.parquet").exists()
    assert (tmp_path / "latest.parquet").exists()


def test_save_snapshot_latest_matches_dated(tmp_path, monkeypatch, sample_df):
    _patch_snapshots_dir(monkeypatch, tmp_path)
    d = date(2025, 1, 15)
    save_snapshot(sample_df, d)

    dated = pd.read_parquet(tmp_path / "2025-01-15.parquet")
    latest = pd.read_parquet(tmp_path / "latest.parquet")
    pd.testing.assert_frame_equal(dated, latest)


def test_save_snapshot_creates_dir_if_missing(tmp_path, monkeypatch, sample_df):
    new_dir = tmp_path / "snapshots"
    monkeypatch.setattr(config_mod, "SNAPSHOTS_DIR", new_dir)
    monkeypatch.setattr(ingest_mod, "SNAPSHOTS_DIR", new_dir)

    assert not new_dir.exists()
    save_snapshot(sample_df, date(2025, 1, 15))
    assert new_dir.exists()


# --- cleanup_old_snapshots ---


def test_cleanup_removes_old_files(tmp_path, monkeypatch):
    monkeypatch.setattr(ingest_mod, "SNAPSHOTS_DIR", tmp_path)

    today = date(2025, 1, 15)
    old_date = today - timedelta(days=SNAPSHOT_RETENTION_DAYS + 1)
    recent_date = today - timedelta(days=1)

    (tmp_path / f"{old_date.isoformat()}.parquet").touch()
    (tmp_path / f"{recent_date.isoformat()}.parquet").touch()

    cleanup_old_snapshots(today)

    assert not (tmp_path / f"{old_date.isoformat()}.parquet").exists()
    assert (tmp_path / f"{recent_date.isoformat()}.parquet").exists()


def test_cleanup_ignores_non_date_files(tmp_path, monkeypatch):
    monkeypatch.setattr(ingest_mod, "SNAPSHOTS_DIR", tmp_path)

    (tmp_path / "latest.parquet").touch()
    (tmp_path / "not-a-date.parquet").touch()

    cleanup_old_snapshots(date(2025, 1, 15))

    assert (tmp_path / "latest.parquet").exists()
    assert (tmp_path / "not-a-date.parquet").exists()
