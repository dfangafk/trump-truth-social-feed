"""Tests for ttsenrich.config — path generation functions."""

from datetime import date

from ttsenrich.config import (
    ENRICHED_OUTPUT_DIR,
    RAW_OUTPUT_DIR,
    enriched_output_path,
    raw_output_path,
)


def test_raw_output_path_format():
    d = date(2025, 1, 15)
    result = raw_output_path(d)
    assert result == RAW_OUTPUT_DIR / "2025-01-15.json"
    assert result.suffix == ".json"


def test_raw_output_path_zero_padding():
    d = date(2025, 1, 5)
    assert "2025-01-05" in str(raw_output_path(d))


def test_enriched_output_path_format():
    d = date(2025, 1, 15)
    result = enriched_output_path(d)
    assert result == ENRICHED_OUTPUT_DIR / "2025-01-15.json"
