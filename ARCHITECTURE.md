# Trump Truth Social Feed — Codebase Guide

A daily pipeline that downloads Trump's Truth Social archive from CNN, filters posts created in the last 24 hours, and produces JSON output of new posts.

---

## Project Structure

```
trump-truth-social-feed/
├── pyproject.toml          # Dependencies, entry point, build config
├── ttsfeed/                # Main package
│   ├── __init__.py
│   ├── config.py           # URLs, paths, constants
│   ├── fetch.py            # Download archive → parse to DataFrame
│   ├── filter.py           # Filter recent posts → emit JSON output
│   └── pipeline.py         # CLI entry point (fetch → filter)
├── tests/
│   ├── conftest.py         # Shared fixtures (sample DataFrames, bytes)
│   ├── test_config.py
│   ├── test_fetch.py
│   ├── test_filter.py
│   └── test_pipeline.py
└── data/                   # Generated at runtime
    └── output/             # Daily JSON output files
```

---

## Module Diagram

```
┌──────────────────────────────────────────────────────────┐
│                     pipeline.py                          │
│                   (CLI entry point)                      │
│                                                          │
│  main() runs:                                            │
│    1. raw, fmt = download_archive()                      │
│    2. df = bytes_to_dataframe(raw, fmt)                  │
│    3. new_posts_df = filter_recent_posts(df)             │
│    4. save_output(new_posts_df, total_archive=len(df))   │
└──────────┬──────────────────────────────┬────────────────┘
           │                              │
           ▼                              ▼
┌─────────────────────┐       ┌─────────────────────────┐
│     fetch.py        │       │       filter.py         │
│                     │       │                         │
│ download_archive()  │       │ filter_recent_posts()   │
│   ↓                 │       │   ↓                     │
│ bytes_to_dataframe()│       │ _post_to_dict()         │
│                     │       │   ↓                     │
│                     │       │ save_output()           │
└────────┬────────────┘       └────────┬────────────────┘
         │                             │
         ▼                             ▼
┌──────────────────────────────────────────────────────────┐
│                      config.py                           │
│                                                          │
│  ARCHIVE_URL_PARQUET / ARCHIVE_URL_JSON   (CNN sources)  │
│  TRUTH_SOCIAL_PROFILE_URL                 (profile URL)  │
│  OUTPUT_DIR                               (output dir)   │
│  output_path(date)                        (path helper)  │
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
filter_recent_posts()       ← keeps posts where created_at >= now - 24h
      │
      ▼
save_output()               ← writes data/output/YYYY-MM-DD.json
                               with new posts + summary stats
```

---

## Module Details

### `config.py` — Constants & Path Helpers

| Export                    | Description                              |
|---------------------------|------------------------------------------|
| `ARCHIVE_URL_PARQUET`     | Primary CNN archive URL (Parquet format) |
| `ARCHIVE_URL_JSON`        | Fallback CNN archive URL (JSON format)   |
| `TRUTH_SOCIAL_PROFILE_URL`| Truth Social profile URL                 |
| `BASE_DIR`                | Repository root                          |
| `OUTPUT_DIR`              | `data/output/`                           |
| `output_path(date)`       | → `data/output/YYYY-MM-DD.json`          |

### `fetch.py` — Download & Parse

| Function                | Role                                           |
|-------------------------|------------------------------------------------|
| `download_archive(url)` | HTTP GET with User-Agent; auto-fallback to JSON |
| `bytes_to_dataframe()`  | Parse bytes → DataFrame; normalize `id` to str |

### `filter.py` — Filter Recent Posts

| Function                | Role                                            |
|-------------------------|-------------------------------------------------|
| `filter_recent_posts()` | Filter DataFrame by `created_at` within window  |
| `_post_to_dict(row)`    | Row → dict with safe NaN/media handling         |
| `save_output()`         | Write JSON: `{as_of, window_hours, summary, new_posts}` |

### `pipeline.py` — CLI Entry Point

```bash
uv run python -m ttsfeed.pipeline   # run for today
```

Calls `download_archive()` → `bytes_to_dataframe()` → `filter_recent_posts()` → `save_output()`, exits with code 1 on fetch errors.

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
- **NaN handling**: Missing count columns default to `0` via safe int parsing.
- **Media normalization**: Accepts both Python lists and JSON-encoded strings.
- **No posts in window**: If no posts are within the 24h window, an empty output is written.

---

## Output JSON Format

```json
{
  "as_of": "2026-02-17T23:30:00Z",
  "window_hours": 24,
  "summary": {
    "total_posts_in_archive": 31577,
    "new_posts_count": 3
  },
  "new_posts": [...]
}
```

---

## Tests

Tests across 4 files. Run with:

```bash
pytest
```

### Coverage by Module

| File              | What's Covered                                                    |
|-------------------|-------------------------------------------------------------------|
| `test_config.py`  | Path formatting, zero-padded dates                                |
| `test_fetch.py`   | Download (success + fallback + failure), parsing (Parquet + JSON), ID normalization, sorting |
| `test_filter.py`  | `filter_recent_posts` (recent/none/all/custom window), `_post_to_dict` (basic fields, list media, JSON-string media, NaN counts, None media), output JSON structure, zero-post output |
| `test_pipeline.py`| Fetch+filter called correctly, fetch failure (exit 1)             |

### Shared Fixtures (`conftest.py`)

| Fixture        | Description                                        |
|----------------|----------------------------------------------------|
| `sample_df`    | 3-row DataFrame with realistic schema (IDs 100–300) |
| `parquet_bytes`| Binary Parquet of `sample_df`                      |
| `json_bytes`   | Binary JSON of `sample_df`                         |

All fetch tests mock HTTP calls; filter tests use timestamps relative to a fixed reference time.
