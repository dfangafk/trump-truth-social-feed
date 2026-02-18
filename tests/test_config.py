"""Tests for ttsfeed.config — path generation functions."""

from datetime import date

from ttsfeed.config import DIFFS_DIR, SNAPSHOTS_DIR, diff_path, latest_snapshot_path, snapshot_path


def test_snapshot_path_format():
    d = date(2025, 1, 15)
    result = snapshot_path(d)
    assert result == SNAPSHOTS_DIR / "2025-01-15.parquet"
    assert result.suffix == ".parquet"


def test_snapshot_path_zero_padding():
    d = date(2025, 1, 5)
    assert "2025-01-05" in str(snapshot_path(d))


def test_latest_snapshot_path():
    result = latest_snapshot_path()
    assert result == SNAPSHOTS_DIR / "latest.parquet"
    assert result.name == "latest.parquet"


def test_diff_path_format():
    d = date(2025, 1, 15)
    result = diff_path(d)
    assert result == DIFFS_DIR / "2025-01-15.json"
    assert result.suffix == ".json"


def test_snapshot_and_diff_in_different_dirs():
    d = date(2025, 1, 15)
    assert snapshot_path(d).parent != diff_path(d).parent
