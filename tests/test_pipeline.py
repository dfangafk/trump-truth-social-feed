"""Tests for ttsfeed.pipeline — CLI orchestrator."""

from datetime import date, timedelta

import pandas as pd
import pytest

from ttsfeed.pipeline import main


def test_main_uses_today_by_default(mocker):
    mock_df = pd.DataFrame({"id": ["1"]})
    mock_ingest = mocker.patch("ttsfeed.pipeline.ingest", return_value=mock_df)
    mock_diff = mocker.patch("ttsfeed.pipeline.run_diff", return_value=0)
    mocker.patch("sys.argv", ["ttsfeed"])

    main()

    today = date.today()
    mock_ingest.assert_called_once_with(today)
    mock_diff.assert_called_once_with(today, today - timedelta(days=1))


def test_main_accepts_date_argument(mocker):
    mock_df = pd.DataFrame({"id": ["1"]})
    mocker.patch("ttsfeed.pipeline.ingest", return_value=mock_df)
    mock_diff = mocker.patch("ttsfeed.pipeline.run_diff", return_value=5)
    mocker.patch("sys.argv", ["ttsfeed", "2025-01-15"])

    main()

    mock_diff.assert_called_once_with(date(2025, 1, 15), date(2025, 1, 14))


def test_main_exits_on_invalid_date(mocker):
    mocker.patch("sys.argv", ["ttsfeed", "not-a-date"])

    with pytest.raises(SystemExit) as exc_info:
        main()
    assert exc_info.value.code == 1


def test_main_exits_on_ingest_failure(mocker):
    mocker.patch("ttsfeed.pipeline.ingest", side_effect=RuntimeError("network down"))
    mocker.patch("sys.argv", ["ttsfeed"])

    with pytest.raises(SystemExit) as exc_info:
        main()
    assert exc_info.value.code == 1
