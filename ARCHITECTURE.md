# Trump Truth Social Feed — Codebase Guide

A daily pipeline that downloads Trump's Truth Social archive from CNN, filters posts created in the last 24 hours, and produces JSON output of new posts.

---

## Project Structure

```
trump-truth-social-feed/
├── pyproject.toml          # Dependencies, entry point, build config
├── ttsfeed/                # Main package
│   ├── __init__.py
│   ├── analyze.py          # LLM enrichment → EnrichResult (summary + categories)
│   ├── config.py           # URLs, paths, constants, POST_CATEGORIES
│   ├── export.py           # Serialize posts to JSON, write daily output files
│   ├── fetch.py            # Download archive → parse to DataFrame → filter recent posts
│   └── pipeline.py         # CLI entry point (fetch → filter → analyze → export)
├── tests/
│   ├── conftest.py         # Shared fixtures (sample DataFrames, bytes)
│   ├── test_analyze.py
│   ├── test_config.py
│   ├── test_export.py
│   ├── test_fetch.py
│   └── test_pipeline.py
└── data/                   # Generated at runtime
    └── output/             # Daily JSON output files
```

---

## Module Diagram

```
┌──────────────────────────────────────────────────────────────┐
│                       pipeline.py                            │
│                     (CLI entry point)                        │
│                                                              │
│  main() runs:                                                │
│    1. raw, fmt = download_archive()                          │
│    2. df = bytes_to_dataframe(raw, fmt)                      │
│    3. new_posts_df = filter_recent_posts(df)                 │
│    4. enrichment = analyze_posts(posts, complete)  [opt]     │
│    5. save_output(new_posts_df, ..., enrichment=enrichment)  │
└──────────┬───────────────────────────┬────────────────────────┘
           │                           │
           ▼                           ▼
┌──────────────────────┐ ┌───────────────┐ ┌─────────────────┐
│       fetch.py       │ │  analyze.py   │ │   export.py     │
│                      │ │               │ │                 │
│ download_archive()   │ │ analyze_      │ │ _post_to_dict() │
│   ↓                  │ │   posts()     │ │   ↓             │
│ bytes_to_dataframe() │ │   ↓           │ │ save_output()   │
│   ↓                  │ │ EnrichResult  │ │                 │
│ filter_recent_       │ │               │ │                 │
│   posts()            │ │               │ │                 │
└──────────┬───────────┘ └───────┬───────┘ └───────┬─────────┘
           │                     │                 │
           ▼                     ▼                 ▼
┌──────────────────────────────────────────────────────────────┐
│                         config.py                            │
│                                                              │
│  ARCHIVE_URL_PARQUET / ARCHIVE_URL_JSON   (CNN sources)      │
│  TRUTH_SOCIAL_PROFILE_URL                 (profile URL)      │
│  OUTPUT_DIR                               (output dir)       │
│  POST_CATEGORIES                          (taxonomy list)    │
│  output_path(date)                        (path helper)      │
└──────────────────────────────────────────────────────────────┘
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
analyze_posts()             ← [optional] LLM call via complete: Callable
      │                        skipped if LLM_MODEL env var is unset
      ▼
save_output()               ← writes data/output/YYYY-MM-DD.json
                               with new posts + summary stats (+ enrichment if set)
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
| `POST_CATEGORIES`         | Fixed taxonomy list for LLM categorization |
| `output_path(date)`       | → `data/output/YYYY-MM-DD.json`          |

### `fetch.py` — Download, Parse & Filter

| Function                | Role                                            |
|-------------------------|-------------------------------------------------|
| `download_archive(url)` | HTTP GET with User-Agent; auto-fallback to JSON |
| `bytes_to_dataframe()`  | Parse bytes → DataFrame; normalize `id` to str  |
| `filter_recent_posts()` | Filter DataFrame by `created_at` within window  |

### `export.py` — Serialization & Output

| Function             | Role                                                                                        |
|----------------------|---------------------------------------------------------------------------------------------|
| `_post_to_dict(row)` | Row → dict with safe NaN/media handling                                                     |
| `save_output()`      | Write JSON: `{as_of, window_hours, summary, new_posts}`; accepts optional `enrichment: EnrichResult` |

### `analyze.py` — LLM Enrichment

| Export                  | Role                                            |
|-------------------------|-------------------------------------------------|
| `EnrichResult`          | Dataclass: `daily_summary: str`, `categories: list[str]` |
| `analyze_posts(posts, complete)` | Build prompt, call `complete: Callable[[str], str]`, parse JSON response → `EnrichResult` |

The `complete` callable is injected by `pipeline.py` (wired to `litellm.completion`), keeping `analyze.py` free of direct LiteLLM imports and fully unit-testable with a plain mock. On any JSON parse failure, `analyze_posts` raises `ValueError` so the caller can catch and skip enrichment gracefully.

### `pipeline.py` — CLI Entry Point

```bash
uv run python -m ttsfeed.pipeline              # run for today (no enrichment)
LLM_MODEL=gpt-4o-mini uv run python -m ttsfeed.pipeline  # with LLM enrichment
```

Calls `download_archive()` → `bytes_to_dataframe()` → `filter_recent_posts()` → `analyze_posts()` (if `LLM_MODEL` env var is set) → `save_output()`, exits with code 1 on fetch errors. LLM failures are caught and logged as warnings; enrichment is skipped silently.

#### `LLM_MODEL` env var

Set `LLM_MODEL` to any [LiteLLM-supported model string](https://docs.litellm.ai/docs/providers) (e.g. `gpt-4o-mini`, `claude-3-5-haiku-20241022`). If unset, enrichment is skipped with no error. Provider API keys (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, etc.) must also be set as appropriate.

---

## Dependencies

| Package    | Purpose                    |
|------------|----------------------------|
| `litellm`  | Model-agnostic LLM calls   |
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

Without enrichment:
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

With enrichment (`LLM_MODEL` set):
```json
{
  "as_of": "2026-02-17T23:30:00Z",
  "window_hours": 24,
  "summary": {
    "total_posts_in_archive": 31577,
    "new_posts_count": 3,
    "daily_summary": "Trump posted primarily about immigration...",
    "categories": ["immigration", "media criticism"]
  },
  "new_posts": [...]
}
```

---

## Tests

Tests across 5 files. Run with:

```bash
pytest
```

### Coverage by Module

| File               | What's Covered                                                    |
|--------------------|-------------------------------------------------------------------|
| `test_analyze.py`  | `analyze_posts`: success path, empty posts, malformed JSON, missing keys, propagated exceptions |
| `test_config.py`   | Path formatting, zero-padded dates                                |
| `test_export.py`   | `_post_to_dict` (basic fields, list media, JSON-string media, NaN counts, None media), `save_output` (JSON structure, zero-post output) |
| `test_fetch.py`    | Download (success + fallback + failure), parsing (Parquet + JSON), ID normalization, sorting, `filter_recent_posts` (recent/none/all/custom window, defaults to now) |
| `test_pipeline.py` | Fetch+filter called correctly, fetch failure (exit 1)             |

### Shared Fixtures (`conftest.py`)

| Fixture        | Description                                        |
|----------------|----------------------------------------------------|
| `sample_df`    | 3-row DataFrame with realistic schema (IDs 100–300) |
| `parquet_bytes`| Binary Parquet of `sample_df`                      |
| `json_bytes`   | Binary JSON of `sample_df`                         |

All fetch tests mock HTTP calls; filter tests use timestamps relative to a fixed reference time.
