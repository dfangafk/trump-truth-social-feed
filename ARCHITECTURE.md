# Trump Truth Social Feed — Codebase Guide

A daily pipeline that downloads Trump's Truth Social archive from CNN, filters posts created in the last 24 hours, and produces JSON output of new posts.

---

## Project Structure

```
trump-truth-social-feed/
├── pyproject.toml          # Dependencies, entry point, build config
├── ttsfeed/                # Main package
│   ├── __init__.py
│   ├── analyze.py          # LLM enrichment → EnrichResult (summary + per-post categories)
│   ├── config.py           # URLs, paths, constants, POST_CATEGORIES
│   ├── export.py           # Serialize posts to JSON, write daily output files
│   ├── fetch.py            # Download archive → parse to DataFrame → filter recent posts
│   ├── llm.py              # LLM provider abstraction — LiteLLM API + `claude -p` + `codex exec` fallbacks
│   └── pipeline.py         # CLI entry point (fetch → filter → save → analyze → save)
├── tests/
│   ├── conftest.py         # Shared fixtures (sample DataFrames, bytes)
│   ├── test_analyze.py
│   ├── test_config.py
│   ├── test_export.py
│   ├── test_fetch.py
│   ├── test_llm.py
│   └── test_pipeline.py
└── data/                   # Generated at runtime
    ├── raw/                # Daily raw JSON output files
    └── enriched/           # Daily enriched JSON output files
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
│    4. save_output(..., output_dir=RAW_OUTPUT_DIR, output_name="YYYY-MM-DD.json") [always] │
│    5. complete = build_complete_fn()          [from llm.py]  │
│    6. enrichment = analyze_posts(posts, complete)  [opt]     │
│    7. save_output(..., enrichment=..., output_dir=ENRICHED_OUTPUT_DIR, output_name="YYYY-MM-DD.json") [opt] │
└──────────┬────────────────────────────┬───────────────────────┘
           │                            │
           ▼                            ▼
┌──────────────────────┐ ┌────────────────────────────────────┐
│       fetch.py       │ │            llm.py                  │
│                      │ │                                    │
│ download_archive()   │ │ build_complete_fn()                │
│   ↓                  │ │   → _call_llm_api / _call_claude_cli / _call_codex_cli / None │
│ bytes_to_dataframe() │ │                                    │
│   ↓                  │ └───────────────┬────────────────────┘
│ filter_recent_       │                 │
│   posts()            │                 ▼
└──────────┬───────────┘  ┌─────────────────────────────────┐
           │              │          analyze.py              │
           │              │                                  │
           │              │  analyze_posts(posts, complete)  │
           │              │    ↓                             │
           │              │  EnrichResult                    │
           │              └──────────────┬──────────────────┘
           │                             │
           ▼                             ▼
┌──────────────────────┐  ┌─────────────────────────────────┐
│       export.py      │  │           config.py              │
│                      │  │                                  │
│ _post_to_dict()      │  │ ARCHIVE_URL_PARQUET/JSON         │
│   ↓                  │  │ TRUTH_SOCIAL_PROFILE_URL         │
│ save_output()        │  │ RAW_OUTPUT_DIR, ENRICHED_OUTPUT_DIR │
│                      │  │ POST_CATEGORIES                  │
└──────────────────────┘  │ raw_output_path(date), enriched_output_path(date) │
                          └──────────────────────────────────┘
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
save_output(output_dir=RAW_OUTPUT_DIR, output_name="YYYY-MM-DD.json")
                           ← phase 1: persist filtered posts immediately
      │
      ▼
build_complete_fn()         ← returns _call_llm_api if `LLM_MODEL` set; else _call_claude_cli if `claude` CLI on PATH; else _call_codex_cli if `codex` on PATH; else None
      │
      ▼
analyze_posts()             ← [optional] LLM call via complete: Callable
      │                        skipped if no API model and no CLI provider available
      ▼
save_output(output_dir=ENRICHED_OUTPUT_DIR, output_name="YYYY-MM-DD.json")
                           ← phase 2: persist enriched output if successful
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
| `RAW_OUTPUT_DIR`          | `data/raw/`                              |
| `ENRICHED_OUTPUT_DIR`     | `data/enriched/`                         |
| `POST_CATEGORIES`         | Fixed taxonomy list for LLM categorization |
| `raw_output_path(date)`   | → `data/raw/YYYY-MM-DD.json`             |
| `enriched_output_path(date)` | → `data/enriched/YYYY-MM-DD.json`    |

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
| `save_output()`      | Write JSON: `{as_of, window_hours, summary, new_posts}`; if enriched, adds `daily_summary` and per-post `categories`; supports explicit output filename |

### `analyze.py` — LLM Enrichment

| Export                  | Role                                            |
|-------------------------|-------------------------------------------------|
| `EnrichResult`          | Dataclass: `daily_summary: str`, `post_categories: dict[str, list[str]]` |
| `analyze_posts(posts, complete)` | Build prompt, call `complete: Callable[[str], str]`, parse JSON response → `EnrichResult` |

The `complete` callable is injected by `pipeline.py` (obtained from `llm.build_complete_fn()`), keeping `analyze.py` free of CLI/subprocess concerns and fully unit-testable with a plain mock. On any JSON parse failure, `analyze_posts` raises `ValueError` so the caller can catch and skip enrichment gracefully.

### `llm.py` — LLM Provider Abstraction

| Export                  | Role                                            |
|-------------------------|-------------------------------------------------|
| `build_complete_fn()`   | Resolution order: `_call_llm_api` if `LLM_MODEL` is set, else `_call_claude_cli` if `claude` is on PATH, else `_call_codex_cli` if `codex` is on PATH, else `None` |
| `_call_llm_api(prompt)` | Calls `litellm.completion(...)` with `response_format={"type":"json_object"}` and returns `response.choices[0].message.content` |
| `_call_claude_cli(prompt)` | Invokes `claude -p` headless CLI with `--output-format json` + `--json-schema`; returns `structured_output` as JSON string |
| `_call_codex_cli(prompt)` | Invokes `codex exec` headless CLI with `--ephemeral`, `--full-auto`, and `--output-schema`; returns stdout JSON string |

Primary path uses LiteLLM for provider-agnostic API calls (set `LLM_MODEL`, e.g. `anthropic/claude-opus-4-6` or `openai/gpt-4o`). LiteLLM reads provider credentials from environment variables such as `ANTHROPIC_API_KEY` and `OPENAI_API_KEY`. Fallback paths use Claude Code CLI (`claude -p`) and Codex CLI (`codex exec`) in headless mode via `subprocess.run`. In CI, if neither API nor CLI provider is configured, `build_complete_fn()` returns `None` and enrichment is silently skipped.

### `pipeline.py` — CLI Entry Point

```bash
uv run python -m ttsfeed.pipeline   # run for today (enrichment if API model, claude CLI, or codex CLI available)
```

Calls `download_archive()` → `bytes_to_dataframe()` → `filter_recent_posts()` → `save_output(..., output_dir=RAW_OUTPUT_DIR, output_name="YYYY-MM-DD.json")` (always) → `build_complete_fn()` → `analyze_posts()` (if `complete` is not `None`) → `save_output(..., enrichment=enrichment, output_dir=ENRICHED_OUTPUT_DIR, output_name="YYYY-MM-DD.json")` (only if enrichment succeeds). Exits with code 1 on fetch errors. LLM failures are caught and logged as warnings, while the raw file remains intact.

---

## Dependencies

| Package    | Purpose                    |
|------------|----------------------------|
| `litellm`  | Unified LLM API client across providers |
| `pandas`   | DataFrame operations       |
| `pyarrow`  | Parquet read/write support |
| `requests` | HTTP archive downloads     |

LLM enrichment prefers LiteLLM API calls when `LLM_MODEL` is set; otherwise it can use the `claude` CLI (Claude Code) or `codex` CLI via `subprocess`.

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

With enrichment (LLM provider configured via `LLM_MODEL`, `claude` CLI, or `codex` CLI on PATH):
```json
{
  "as_of": "2026-02-17T23:30:00Z",
  "window_hours": 24,
  "summary": {
    "total_posts_in_archive": 31577,
    "new_posts_count": 3,
    "daily_summary": "Trump posted primarily about immigration..."
  },
  "new_posts": [
    {
      "id": "123",
      "content": "...",
      "categories": ["immigration", "media criticism"]
    }
  ]
}
```

---

## Tests

Tests across 6 files. Run with:

```bash
pytest
```

### Coverage by Module

| File               | What's Covered                                                    |
|--------------------|-------------------------------------------------------------------|
| `test_analyze.py`  | `analyze_posts`: success path, empty posts, malformed JSON, missing keys, propagated exceptions |
| `test_config.py`   | Path formatting, zero-padded dates                                |
| `test_export.py`   | `_post_to_dict` (basic fields, list media, JSON-string media, NaN counts, None media), `save_output` (JSON structure, zero-post output, per-post enrichment categories) |
| `test_fetch.py`    | Download (success + fallback + failure), parsing (Parquet + JSON), ID normalization, sorting, `filter_recent_posts` (recent/none/all/custom window, defaults to now) |
| `test_llm.py`      | `build_complete_fn`: API/Claude/Codex/None selection; `_call_llm_api`: success + propagated provider errors; `_call_claude_cli`: success path, non-zero exit code, missing structured_output key; `_call_codex_cli`: success + non-zero exit |
| `test_pipeline.py` | Two-phase save behavior (no LLM, LLM success, LLM failure) and fetch failure (exit 1) |

### Shared Fixtures (`conftest.py`)

| Fixture        | Description                                        |
|----------------|----------------------------------------------------|
| `sample_df`    | 3-row DataFrame with realistic schema (IDs 100–300) |
| `parquet_bytes`| Binary Parquet of `sample_df`                      |
| `json_bytes`   | Binary JSON of `sample_df`                         |

All fetch tests mock HTTP calls; filter tests use timestamps relative to a fixed reference time.
