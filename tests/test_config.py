"""Tests for ttsfeed.config — path generation functions."""

from datetime import date

from ttsfeed.config import OUTPUT_DIR, output_path


def test_output_path_format():
    d = date(2025, 1, 15)
    result = output_path(d)
    assert result == OUTPUT_DIR / "2025-01-15.json"
    assert result.suffix == ".json"


def test_output_path_zero_padding():
    d = date(2025, 1, 5)
    assert "2025-01-05" in str(output_path(d))
