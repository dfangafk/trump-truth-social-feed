# Project Instructions

## Overview

Daily ingestion pipeline for Trump's Truth Social archive. Downloads posts from a CNN-hosted dataset, stores daily Parquet snapshots, detects new posts via diffing, and outputs JSON diffs. Runs automatically via GitHub Actions.

## Key Commands

```bash
uv sync                                    # Install all dependencies
uv run python -m ttsfeed.pipeline          # Run pipeline for today
uv run python -m ttsfeed.pipeline 2025-01-15  # Backfill a specific date
pytest                                     # Run all 35 tests
pytest tests/test_ingest.py -v             # Run a specific test file
```

## Project Structure

- `ttsfeed/` — Flat package layout (no sub-packages)
  - `config.py` — Constants, paths, helper functions
  - `ingest.py` — Download archive, parse, save snapshots, cleanup
  - `diff.py` — Compare snapshots, detect new posts, emit JSON diffs
  - `pipeline.py` — CLI entry point combining ingest + diff
- `tests/` — pytest tests with shared fixtures in `conftest.py`
- `data/snapshots/` — Daily Parquet files + `latest.parquet`
- `data/diffs/` — Daily JSON diff files

## Architecture Documentation

When making code changes that affect the project structure, module interfaces, data flow, or public API (e.g., adding/removing/renaming modules, functions, constants, or changing dependencies), update `ARCHITECTURE.md` to keep it in sync. Routine bug fixes or minor edits that don't change the architecture do not require an update.

## Code Conventions

- **Python 3.12+** — Use modern syntax (e.g., `X | Y` union types, not `Union[X, Y]`)
- All module imports at the top of the file, never inside functions
- No unused imports
- Snake_case for functions/variables, UPPER_CASE for module-level constants
- Use `logging.getLogger(__name__)` for module loggers
- Type hints on all public function signatures
- Docstrings on modules and public functions

## Testing

- Framework: pytest + pytest-mock
- Fixtures defined in `tests/conftest.py` (`sample_df`, `sample_df_yesterday`, `parquet_bytes`, `json_bytes`)
- Tests rely heavily on mocking external calls (HTTP, filesystem) — never make real network requests in tests
- Run `pytest` before committing to verify nothing is broken

## CI/CD

- `.github/workflows/daily_ingest.yml` runs daily at 23:30 UTC
- Commits results with bot user `github-actions[bot]`
- Only `data/diffs/` and `data/snapshots/latest.parquet` are committed (old snapshots are gitignored)