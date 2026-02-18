# Trump Truth Social Feed — Codebase Guide

A daily ingestion pipeline that downloads Trump's Truth Social archive from CNN, stores snapshots as Parquet files, and produces JSON diffs of new posts.

---

## Project Structure

```
trump-truth-social-feed/
├── pyproject.toml          # Dependencies, entry point, build config
├── ttsfeed/                # Main package
│   ├── __init__.py
│   ├── config.py           # URLs, paths, constants
│   ├── ingest.py           # Download archive → save snapshot
│   ├── diff.py             # Compare snapshots → emit new-post diffs
│   └── pipeline.py         # CLI entry point (ingest → diff)
├── tests/
│   ├── conftest.py         # Shared fixtures (sample DataFrames, bytes)
│   ├── test_config.py
│   ├── test_ingest.py
│   ├── test_diff.py
│   └── test_pipeline.py
└── data/                   # Generated at runtime
    ├── snapshots/          # Daily Parquet files + latest.parquet
    └── diffs/              # Daily JSON diffs
```

---

## Module Diagram

```
┌──────────────────────────────────────────────────────────┐
│                     pipeline.py                          │
│                   (CLI entry point)                      │
│                                                          │
│  main() parses CLI args, then runs:                      │
│    1. ingest(date)                                       │
│    2. run_diff(today, yesterday)                         │
└──────────┬──────────────────────────────┬────────────────┘
           │                              │
           ▼                              ▼
┌─────────────────────┐       ┌─────────────────────────┐
│     ingest.py       │       │        diff.py          │
│                     │       │                         │
│ download_archive()  │       │ load_snapshot()         │
│   ↓                 │       │   ↓                     │
│ bytes_to_dataframe()│       │ find_new_posts()        │
│   ↓                 │       │   ↓                     │
│ save_snapshot()     │       │ _post_to_dict()         │
│   ↓                 │       │   ↓                     │
│ cleanup_old_snaps() │       │ save_diff()             │
└────────┬────────────┘       └────────┬────────────────┘
         │                             │
         ▼                             ▼
┌──────────────────────────────────────────────────────────┐
│                      config.py                           │
│                                                          │
│  ARCHIVE_URL_PARQUET / ARCHIVE_URL_JSON   (CNN sources)  │
│  SNAPSHOTS_DIR / DIFFS_DIR                (output dirs)  │
│  SNAPSHOT_RETENTION_DAYS = 7                             │
│  snapshot_path(date) / diff_path(date)    (path helpers) │
└──────────────────────────────────────────────────────────┘
```

### Data Flow

```
CNN Archive (Parquet or JSON)
      │
      ▼
download_archive()          ← tries Parquet first, falls back to JSON
      │
      ▼
bytes_to_dataframe()        ← normalizes IDs to str, sorts by ID
      │
      ▼
save_snapshot(df, date)     ← writes data/snapshots/YYYY-MM-DD.parquet
      │                        + copies to latest.parquet (for CI)
      ▼
cleanup_old_snapshots()     ← removes files older than 7 days
      │
      ▼
load_snapshot(today)   ─┐
load_snapshot(yesterday)┤   ← falls back to latest.parquet if yesterday missing
                        │
                        ▼
               find_new_posts()
                        │
                        ▼
               save_diff()              ← writes data/diffs/YYYY-MM-DD.json
                                           with new posts + summary stats
```

---

## Module Details

### `config.py` — Constants & Path Helpers

| Export                    | Description                                     |
|---------------------------|-------------------------------------------------|
| `ARCHIVE_URL_PARQUET`     | Primary CNN archive URL (Parquet format)         |
| `ARCHIVE_URL_JSON`        | Fallback CNN archive URL (JSON format)           |
| `BASE_DIR`                | Repository root                                  |
| `SNAPSHOTS_DIR`           | `data/snapshots/`                                |
| `DIFFS_DIR`               | `data/diffs/`                                    |
| `SNAPSHOT_RETENTION_DAYS` | 7                                                |
| `snapshot_path(date)`     | → `data/snapshots/YYYY-MM-DD.parquet`            |
| `latest_snapshot_path()`  | → `data/snapshots/latest.parquet`                |
| `diff_path(date)`         | → `data/diffs/YYYY-MM-DD.json`                   |

### `ingest.py` — Download & Store

| Function                  | Role                                             |
|---------------------------|--------------------------------------------------|
| `download_archive(url)`   | HTTP GET with User-Agent; auto-fallback to JSON  |
| `bytes_to_dataframe()`    | Parse bytes → DataFrame; normalize `id` to str   |
| `save_snapshot(df, date)` | Write dated `.parquet` + copy to `latest.parquet` |
| `cleanup_old_snapshots()` | Delete snapshots older than 7 days               |
| `ingest(date)`            | Orchestrator: download → parse → save → cleanup  |

### `diff.py` — Detect New Posts

| Function                  | Role                                             |
|---------------------------|--------------------------------------------------|
| `load_snapshot(date)`     | Read `.parquet` → DataFrame (or `None`)          |
| `find_new_posts()`        | Set-difference on `id` between today/yesterday   |
| `_post_to_dict(row)`      | Row → dict with safe NaN/media handling          |
| `save_diff()`             | Write JSON: `{date_from, date_to, summary, new_posts}` |
| `run_diff(today, yday)`   | Orchestrator with graceful fallbacks             |

### `pipeline.py` — CLI Entry Point

```bash
ttsfeed              # run for today
ttsfeed 2025-01-15   # backfill a specific date
```

Parses an optional `YYYY-MM-DD` argument, runs `ingest()` then `run_diff()`, and exits with code 1 on errors.

---

## Dependencies

| Package    | Purpose                    |
|------------|----------------------------|
| `pandas`   | DataFrame operations       |
| `pyarrow`  | Parquet read/write support |
| `requests` | HTTP archive downloads     |

Dev: `pytest`, `pytest-mock`

---

## Resilience / Edge Cases

- **Format fallback**: Parquet download fails → retries with JSON URL.
- **CI persistence**: `latest.parquet` survives across CI runs so diffs work even without yesterday's dated file.
- **NaN handling**: Missing count columns default to `0` via safe int parsing.
- **Media normalization**: Accepts both Python lists and JSON-encoded strings.
- **First-run safety**: If no previous snapshot exists, diff is skipped gracefully (returns 0).
- **Retention**: Old snapshots auto-pruned after 7 days; non-date filenames (like `latest.parquet`) are ignored.

---

## Tests

29 tests across 4 files. Run with:

```bash
pytest
```

### Coverage by Module

| File              | Tests | What's Covered                                                    |
|-------------------|-------|-------------------------------------------------------------------|
| `test_config.py`  | 5     | Path formatting, zero-padded dates, directory separation          |
| `test_ingest.py`  | 11    | Download (success + fallback + failure), parsing (Parquet + JSON), ID normalization, sorting, snapshot save, latest copy, dir creation, old-file cleanup |
| `test_diff.py`    | 9     | New-post detection (partial/identical/all-new), `_post_to_dict` (basic fields, list media, JSON-string media, NaN counts, None media), diff JSON structure, zero-post diff, missing-snapshot handling, latest.parquet fallback, end-to-end integration |
| `test_pipeline.py`| 4     | Default date, CLI date arg, invalid date (exit 1), ingest failure (exit 1) |

### Shared Fixtures (`conftest.py`)

| Fixture               | Description                                       |
|------------------------|---------------------------------------------------|
| `sample_df`            | 3-row DataFrame with realistic schema (IDs 100–300) |
| `sample_df_yesterday`  | 1-row subset simulating previous day              |
| `parquet_bytes`        | Binary Parquet of `sample_df`                     |
| `json_bytes`           | Binary JSON of `sample_df`                        |

All ingest tests mock HTTP calls; all diff tests use on-disk temp files via `tmp_path`.
