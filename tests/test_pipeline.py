"""Tests for ttsfeed.pipeline — CLI orchestrator."""

from ttsfeed.config import ENRICHED_OUTPUT_DIR, RAW_OUTPUT_DIR
import pandas as pd
import pytest

from ttsfeed.pipeline import main


def test_main_no_llm_saves_once(mocker):
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
    mock_now = pd.Timestamp("2025-06-15T12:00:00Z")
    mocker.patch("ttsfeed.pipeline.pd.Timestamp.now", return_value=mock_now)
    mocker.patch("ttsfeed.pipeline.os.environ.get", return_value=None)

    main()

    mock_download.assert_called_once()
    mock_parse.assert_called_once_with(b"raw", "parquet")
    mock_filter.assert_called_once_with(mock_df)
    mock_save.assert_called_once_with(
        mock_df,
        total_archive=len(mock_df),
        reference_time=mock_now,
        output_dir=RAW_OUTPUT_DIR,
        output_name="2025-06-15.json",
    )


def test_main_with_llm_saves_twice(mocker):
    mock_df = pd.DataFrame({"id": ["1"], "created_at": ["2025-01-15T10:00:00Z"]})
    mocker.patch("ttsfeed.pipeline.download_archive", return_value=(b"raw", "parquet"))
    mocker.patch("ttsfeed.pipeline.bytes_to_dataframe", return_value=mock_df)
    mocker.patch("ttsfeed.pipeline.filter_recent_posts", return_value=mock_df)
    mock_now = pd.Timestamp("2025-06-15T12:00:00Z")
    mocker.patch("ttsfeed.pipeline.pd.Timestamp.now", return_value=mock_now)
    mocker.patch("ttsfeed.pipeline.os.environ.get", return_value="gpt-4o-mini")
    enrichment = mocker.Mock(daily_summary="summary", post_categories={"1": ["cat"]})
    mock_analyze = mocker.patch("ttsfeed.pipeline.analyze_posts", return_value=enrichment)
    mock_save = mocker.patch("ttsfeed.pipeline.save_output")

    main()

    mock_analyze.assert_called_once()
    assert mock_save.call_count == 2
    first_call = mock_save.call_args_list[0]
    second_call = mock_save.call_args_list[1]
    assert first_call.kwargs == {
        "total_archive": len(mock_df),
        "reference_time": mock_now,
        "output_dir": RAW_OUTPUT_DIR,
        "output_name": "2025-06-15.json",
    }
    assert first_call.args == (mock_df,)
    assert second_call.kwargs == {
        "total_archive": len(mock_df),
        "reference_time": mock_now,
        "enrichment": enrichment,
        "output_dir": ENRICHED_OUTPUT_DIR,
        "output_name": "2025-06-15.json",
    }
    assert second_call.args == (mock_df,)


def test_main_llm_failure_saves_once(mocker):
    mock_df = pd.DataFrame({"id": ["1"], "created_at": ["2025-01-15T10:00:00Z"]})
    mocker.patch("ttsfeed.pipeline.download_archive", return_value=(b"raw", "parquet"))
    mocker.patch("ttsfeed.pipeline.bytes_to_dataframe", return_value=mock_df)
    mocker.patch("ttsfeed.pipeline.filter_recent_posts", return_value=mock_df)
    mock_now = pd.Timestamp("2025-06-15T12:00:00Z")
    mocker.patch("ttsfeed.pipeline.pd.Timestamp.now", return_value=mock_now)
    mocker.patch("ttsfeed.pipeline.os.environ.get", return_value="gpt-4o-mini")
    mocker.patch(
        "ttsfeed.pipeline.analyze_posts",
        side_effect=RuntimeError("llm failed"),
    )
    mock_save = mocker.patch("ttsfeed.pipeline.save_output")

    main()

    mock_save.assert_called_once_with(
        mock_df,
        total_archive=len(mock_df),
        reference_time=mock_now,
        output_dir=RAW_OUTPUT_DIR,
        output_name="2025-06-15.json",
    )


def test_main_exits_on_fetch_failure(mocker):
    mocker.patch(
        "ttsfeed.pipeline.download_archive",
        side_effect=RuntimeError("network down"),
    )

    with pytest.raises(SystemExit) as exc_info:
        main()
    assert exc_info.value.code == 1
