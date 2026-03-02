"""Tests for ttsfeed.pipeline — CLI orchestrator."""

import pandas as pd
import pytest

from ttsfeed.config import settings
from ttsfeed.pipeline import main


def test_main_no_llm_saves_once(mocker):
    mock_df = pd.DataFrame({"id": ["1"], "created_at": ["2025-01-15T10:00:00Z"]})
    mock_download = mocker.patch(
        "ttsfeed.pipeline.download_archive",
        return_value=b"raw",
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
    mocker.patch("ttsfeed.pipeline.build_complete_fn", return_value=None)
    mocker.patch("ttsfeed.pipeline.send_notification")

    main()

    mock_download.assert_called_once()
    mock_parse.assert_called_once_with(b"raw")
    mock_filter.assert_called_once_with(mock_df, hours=24)
    mock_save.assert_called_once_with(
        mock_df,
        total_archive=len(mock_df),
        reference_time=mock_now,
        output_path=settings.paths.raw_output_dir / "2025-06-15.json",
    )


def test_main_with_llm_saves_twice(mocker):
    mock_df = pd.DataFrame({"id": ["1"], "created_at": ["2025-01-15T10:00:00Z"]})
    mocker.patch("ttsfeed.pipeline.download_archive", return_value=b"raw")
    mocker.patch("ttsfeed.pipeline.bytes_to_dataframe", return_value=mock_df)
    mocker.patch("ttsfeed.pipeline.filter_recent_posts", return_value=mock_df)
    mock_now = pd.Timestamp("2025-06-15T12:00:00Z")
    mocker.patch("ttsfeed.pipeline.pd.Timestamp.now", return_value=mock_now)
    mock_complete = mocker.Mock(return_value='{"summary":"x","post_categories":{"1":["cat"]}}')
    mocker.patch("ttsfeed.pipeline.build_complete_fn", return_value=mock_complete)
    enrichment = mocker.Mock(daily_summary="summary", post_categories={"1": ["cat"]})
    mock_analyze = mocker.patch("ttsfeed.pipeline.analyze_posts", return_value=enrichment)
    mock_save = mocker.patch("ttsfeed.pipeline.save_output")
    mocker.patch("ttsfeed.pipeline.send_notification")

    main()

    mock_analyze.assert_called_once()
    analyze_args = mock_analyze.call_args.args
    assert analyze_args[1] is mock_complete
    assert len(analyze_args[0]) == 1
    assert analyze_args[0][0]["id"] == "1"
    assert mock_save.call_count == 2
    first_call = mock_save.call_args_list[0]
    second_call = mock_save.call_args_list[1]
    assert first_call.kwargs == {
        "total_archive": len(mock_df),
        "reference_time": mock_now,
        "output_path": settings.paths.raw_output_dir / "2025-06-15.json",
    }
    assert first_call.args == (mock_df,)
    assert second_call.kwargs == {
        "total_archive": len(mock_df),
        "reference_time": mock_now,
        "enrichment": enrichment,
        "output_path": settings.paths.enriched_output_dir / "2025-06-15.json",
    }
    assert second_call.args == (mock_df,)


def test_main_llm_failure_saves_once(mocker):
    mock_df = pd.DataFrame({"id": ["1"], "created_at": ["2025-01-15T10:00:00Z"]})
    mocker.patch("ttsfeed.pipeline.download_archive", return_value=b"raw")
    mocker.patch("ttsfeed.pipeline.bytes_to_dataframe", return_value=mock_df)
    mocker.patch("ttsfeed.pipeline.filter_recent_posts", return_value=mock_df)
    mock_now = pd.Timestamp("2025-06-15T12:00:00Z")
    mocker.patch("ttsfeed.pipeline.pd.Timestamp.now", return_value=mock_now)
    mock_complete = mocker.Mock(return_value='{"summary":"x","post_categories":{"1":["cat"]}}')
    mocker.patch("ttsfeed.pipeline.build_complete_fn", return_value=mock_complete)
    mocker.patch(
        "ttsfeed.pipeline.analyze_posts",
        side_effect=RuntimeError("llm failed"),
    )
    mock_save = mocker.patch("ttsfeed.pipeline.save_output")
    mocker.patch("ttsfeed.pipeline.send_notification")

    main()

    mock_save.assert_called_once_with(
        mock_df,
        total_archive=len(mock_df),
        reference_time=mock_now,
        output_path=settings.paths.raw_output_dir / "2025-06-15.json",
    )


def test_main_exits_on_fetch_failure(mocker):
    mocker.patch(
        "ttsfeed.pipeline.download_archive",
        side_effect=RuntimeError("network down"),
    )

    with pytest.raises(SystemExit) as exc_info:
        main()
    assert exc_info.value.code == 1
