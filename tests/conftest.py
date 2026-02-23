"""Shared fixtures for Truth Social feed tests."""

import pandas as pd
import pytest


@pytest.fixture(autouse=True)
def no_file_logging(mocker):
    """Prevent pipeline tests from writing real log files to disk."""
    mocker.patch("ttsfeed.pipeline._add_file_handler")


@pytest.fixture
def sample_df():
    """Minimal DataFrame mimicking the real archive schema."""
    return pd.DataFrame({
        "id": ["100", "200", "300"],
        "created_at": [
            "2025-01-14T10:00:00Z",
            "2025-01-15T10:00:00Z",
            "2025-01-15T11:00:00Z",
        ],
        "content": ["Hello world", "Another post", "Third post"],
        "url": [
            "https://truthsocial.com/@realDonaldTrump/100",
            "https://truthsocial.com/@realDonaldTrump/200",
            "https://truthsocial.com/@realDonaldTrump/300",
        ],
        "replies_count": [1, 2, 3],
        "reblogs_count": [4, 5, 6],
        "favourites_count": [7, 8, 9],
        "media": [[], [], []],
    })


@pytest.fixture
def json_bytes(sample_df):
    """Valid JSON bytes for sample_df."""
    return sample_df.to_json(orient="records").encode()
