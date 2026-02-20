"""Tests for ttsfeed.pipeline — CLI orchestrator."""

import pandas as pd
import pytest

from ttsfeed.pipeline import main


def test_main_calls_fetch_and_filter(mocker):
    mock_df = pd.DataFrame({"id": ["1"], "created_at": ["2025-01-15T10:00:00Z"]})
    mock_download = mocker.patch(
        "ttsfeed.pipeline.download_archive",
        return_value=(b"raw", "parquet"),
    )
    mock_parse = mocker.patch(
        "ttsfeed.pipeline.bytes_to_dataframe",
        return_value=mock_df,
    )
    mock_filter = mocker.patch(
        "ttsfeed.pipeline.filter_recent_posts",
        return_value=mock_df,
    )
    mock_save = mocker.patch("ttsfeed.pipeline.save_output")

    main()

    mock_download.assert_called_once()
    mock_parse.assert_called_once_with(b"raw", "parquet")
    mock_filter.assert_called_once_with(mock_df)
    mock_save.assert_called_once_with(mock_df, total_archive=len(mock_df), enrichment=None)


def test_main_exits_on_fetch_failure(mocker):
    mocker.patch(
        "ttsfeed.pipeline.download_archive",
        side_effect=RuntimeError("network down"),
    )

    with pytest.raises(SystemExit) as exc_info:
        main()
    assert exc_info.value.code == 1
