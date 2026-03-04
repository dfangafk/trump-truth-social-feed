# Trump Truth Social Enrich — Codebase Guide

A daily pipeline that downloads Trump's Truth Social archive from CNN, filters posts created in the last 24 hours, and produces LLM-enriched JSON output of new posts.

---

## Project Structure

```
trump-truth-social-feed/
├── pyproject.toml          # Dependencies, entry point, build config
├── settings.toml           # User-editable behavior settings (version-controlled)
├── .env                    # Secrets only — never committed (API keys, email creds)
├── ttsfeed/                # Main package
│   ├── __init__.py
│   ├── analyze.py          # LLM enrichment → EnrichResult (summary + per-post categories)
│   ├── config.py           # URLs, paths, output dirs; LLM/category aliases from settings
│   ├── export.py           # Serialize posts to JSON, write daily output files
│   ├── fetch.py            # Download archive → parse to DataFrame → filter recent posts
│   ├── llm.py              # LLM provider abstraction — explicit `LLM_PROVIDER` selection + auto fallback
│   ├── notify.py           # Email digest after enrichment — fails silently if credentials absent
│   ├── pipeline.py         # CLI entry point (fetch → filter → save → analyze → save → notify)
│   ├── config.py           # URLs, paths, output dirs, settings dataclasses, TOML loader
├── tests/
│   ├── conftest.py         # Shared fixtures (sample DataFrames, bytes)
│   ├── test_analyze.py
│   ├── test_config.py
│   ├── test_export.py
│   ├── test_fetch.py
│   ├── test_llm.py
│   ├── test_pipeline.py
└── data/                   # Generated at runtime
    ├── raw/                # Daily raw JSON output files
    ├── enriched/           # Daily enriched JSON output files
    └── logs/               # Daily run summary JSON files
```

---

## Module Diagram

```
┌──────────────────────────────────────────────────────────────┐
│                       pipeline.py                            │
│                     (CLI entry point)                        │
│                                                              │
│  main() runs:                                                │
│    1. raw = download_archive()                               │
│    2. df = bytes_to_dataframe(raw)                           │
│    3. new_posts_df = filter_recent_posts(df)                 │
│    4. save_output(..., output_dir=RAW_OUTPUT_DIR, output_name="YYYY-MM-DD.json") [always] │
│    5. complete = build_complete_fn()          [from llm.py]  │
│    6. enrichment = analyze_posts(posts, complete)  [opt]     │
│    7. save_output(..., enrichment=..., output_dir=ENRICHED_OUTPUT_DIR, output_name="YYYY-MM-DD.json") [opt] │
│    8. send_notification(reference_time, new_posts, enrichment) [from notify.py] │
│    9. _write_run_summary(run_date, t0, t1, ...)  [always]    │
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
│ _post_to_dict()      │  │ ARCHIVE_URL_JSON                 │
│   ↓                  │  │ TRUTH_SOCIAL_PROFILE_URL         │
│ save_output()        │  │ RAW_OUTPUT_DIR, ENRICHED_OUTPUT_DIR │
│                      │  │ settings (LLM/prompt/pipeline)   │
└──────────────────────┘  └──────────────────────────────────┘
```

### Data Flow

```
CNN Archive (JSON)
      │
      ▼
download_archive()          ← HTTP GET, returns raw bytes
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
build_complete_fn()         ← honors `LLM_PROVIDER` (`api`/`claude_code_cli`/`codex_cli`/`auto`); in `auto`, resolves API (`LLM_MODEL`) → Claude CLI → Codex CLI → None
      │
      ▼
analyze_posts()             ← [optional] LLM call via complete: Callable
      │                        skipped if no API model and no CLI provider available
      ▼
save_output(output_dir=ENRICHED_OUTPUT_DIR, output_name="YYYY-MM-DD.json")
                           ← phase 2: persist enriched output if successful
      │
      ▼
send_notification()         ← [optional] send Gmail digest; skipped if SMTP credentials absent
      │
      ▼
_write_run_summary()        ← [always] write run log to data/logs/YYYY-MM-DD.json
```

---

## Module Details

### `config.py` — Settings Dataclasses, TOML Loader & Constants

Settings live in `config.py` (no separate `settings.py` module). `load_settings()` reads
`settings.toml` at the repo root using `tomllib` (stdlib, Python 3.11+) and is called once
at module import time; the result is exposed as the module-level `settings` singleton.

| Dataclass         | Fields                                                         |
|-------------------|----------------------------------------------------------------|
| `LLMSettings`     | `provider`, `models`, `api_kwargs: dict[str, Any]` — open passthrough dict forwarded directly to `litellm.completion()`; any litellm kwarg accepted; defaults to `{"num_retries": 3}` |
| `PipelineSettings`| `hours`, `log_level`, `schedule` (informational), `save_raw` (bool, default `False`), `save_enriched` (bool, default `False`), `save_logs` (bool, default `False`) — the three save flags can be disabled via `settings.toml` or env vars (`PIPELINE__SAVE_RAW=false`, etc.) |
| `PromptSettings`  | `template`, `categories` — both have hardcoded defaults so the pipeline works without `settings.toml` |
| `Settings`        | `pipeline`, `llm`, `prompt`                                   |

**`settings.toml`** — ships with the repo as the reference config. Contains all tunable
behavior (`[pipeline]`, `[llm]`, `[llm.api_kwargs]`, `[prompt]`). Secrets (API keys, SMTP
credentials) stay in `.env` and are never committed. Categories and the prompt template are
defined under `[prompt]` in the TOML file, with hardcoded fallback defaults in `PromptSettings`
for installs that do not include the TOML file.

**Constants exported by `config.py`:**

| Export                    | Description                              |
|---------------------------|------------------------------------------|
| `ARCHIVE_URL_JSON`        | CNN archive URL (JSON format)            |
| `TRUTH_SOCIAL_PROFILE_URL`| Truth Social profile URL                 |
| `BASE_DIR`                | Repository root                          |
| `RAW_OUTPUT_DIR`          | `data/raw/`                              |
| `ENRICHED_OUTPUT_DIR`     | `data/enriched/`                         |
| `LOGS_OUTPUT_DIR`         | `data/logs/`                             |
| `SENDER_GMAIL`            | Dotenv/env-backed Gmail sender address — must be `@gmail.com` (empty = notify disabled) |
| `GMAIL_APP_PASSWORD`      | Dotenv/env-backed Gmail App Password (16-char) |
| `RECEIVER_EMAIL`          | Dotenv/env-backed recipient address (any provider) |
| `settings`                | Module-level `Settings` singleton (use `settings.llm.provider`, `settings.prompt.template`, etc.) |

`config.py` calls `load_dotenv()` at import time so local `.env` values are loaded once.

---

### `fetch.py` — Download, Parse & Filter

| Function                | Role                                            |
|-------------------------|-------------------------------------------------|
| `download_archive()` | HTTP GET with User-Agent; returns raw bytes     |
| `bytes_to_dataframe()`  | Parse bytes → DataFrame; normalize `id` to str  |
| `filter_recent_posts()` | Filter DataFrame by `created_at` within window  |

### `export.py` — Serialization & Output

| Function             | Role                                                                                        |
|----------------------|---------------------------------------------------------------------------------------------|
| `_post_to_dict(row)` | Row → dict with safe NaN/media handling                                                     |
| `save_output()`      | Write JSON: `{as_of, window_hours, summary, new_posts}`; if enriched, adds `daily_summary`, per-post `categories`, and `is_reblog` (True/False for posts with content; absent for empty posts); supports explicit output filename |

### `analyze.py` — LLM Enrichment

| Export                  | Role                                            |
|-------------------------|-------------------------------------------------|
| `ENRICHMENT_SCHEMA`     | JSON schema string enforcing `{"summary": ..., "posts": [...]}` response format; shared with `llm.py` CLI providers |
| `EnrichResult`          | Dataclass: `daily_summary: str`, `post_categories: dict[str, list[str]]`, `post_is_reblog: dict[str, bool]` |
| `_is_reblog(post)`      | Returns `True` if `content` starts with `"RT "` |
| `_has_content(post)`    | Returns `True` if `content.strip()` is non-empty |
| `analyze_posts(posts, complete)` | Pre-filter posts; batch substantive posts to LLM; parse response → `EnrichResult` |

**Pre-filter logic** (runs before any LLM call):
- **Empty content** (`content.strip() == ""`): media/link post → `categories: []`, no `is_reblog` entry
- **Reblog** (`content.startswith("RT ")`): repost → `categories: [], is_reblog: True`
- **Substantive**: has text content → batched in single LLM call → `categories: [...]`, `is_reblog: False`

**LLM response schema** (substantive posts only):
```json
{"summary": "2-3 sentence overview", "posts": [{"id": "...", "categories": ["..."]}]}
```

The `complete` callable is injected by `pipeline.py` (obtained from `llm.build_complete_fn()`), keeping `analyze.py` free of CLI/subprocess concerns and fully unit-testable with a plain mock. On any JSON parse failure, `analyze_posts` raises `ValueError` so the caller can catch and skip enrichment gracefully.

### `llm.py` — LLM Provider Abstraction

| Export                  | Role                                            |
|-------------------------|-------------------------------------------------|
| `build_complete_fn()`   | Provider selection via `LLM_PROVIDER` (`api`, `claude_code_cli`, `codex_cli`, `auto`); `auto` resolution: `_call_llm_api` if `LLM_MODELS` set, else `_call_claude_cli` if `claude` on PATH, else `_call_codex_cli` if `codex` on PATH, else `None` |
| `_call_llm_api(prompt)` | Calls `litellm.completion(...)` with `response_format={"type":"json_object"}` and returns `response.choices[0].message.content` |
| `_call_claude_cli(prompt)` | Invokes `claude -p` headless CLI with `--output-format json` + `--json-schema`; returns `structured_output` as JSON string |
| `_call_codex_cli(prompt)` | Invokes `codex exec` headless CLI with `--ephemeral`, `--full-auto`, and `--output-schema`; returns stdout JSON string |

`LLM_PROVIDER` controls which provider is used: `api`, `claude_code_cli`, `codex_cli`, or `auto` (default). `llm.py` reads `LLM_PROVIDER` and `LLM_MODELS` from `config.py`, where they are loaded from `.env`/environment at startup. `llm.py` imports `ENRICHMENT_SCHEMA` from `analyze.py` (domain knowledge co-located with `_PROMPT_TEMPLATE`). In `api` mode, `LLM_MODELS` must be set (e.g. `'["gemini/gemini-2.5-flash","openai/gpt-4o"]'`) and models are tried in order; LiteLLM reads credentials from environment variables such as `GEMINI_API_KEY` and `OPENAI_API_KEY`. `claude_code_cli` and `codex_cli` target their CLIs (`claude -p` and `codex exec`) in headless/non-interactive operation, intended for local testing. In `auto`, selection falls back API → Claude CLI → Codex CLI. If the requested provider is unavailable, `build_complete_fn()` returns `None` and enrichment is skipped.

### `notify.py` — Email Notification

| Export                    | Role                                                              |
|---------------------------|-------------------------------------------------------------------|
| `NotifyFn`                | Type alias `Callable[[pd.Timestamp, list[dict], EnrichResult \| None], None]` — use to type-hint custom notifiers. |
| `send_notification(reference_time, new_posts, enrichment)` | Build and send daily digest email via Gmail SMTP SSL (port 465). Skips silently if `SENDER_GMAIL`, `GMAIL_APP_PASSWORD`, or `RECEIVER_EMAIL` are unset. Catches all send errors and logs as warnings so the pipeline never fails due to email issues. |

Subject: `Trump Truth Social — YYYY-MM-DD (N new posts)`. Body includes date, post count, daily summary (or "Enrichment not available." if enrichment is `None`), and per-post content, categories, and URL.

### `pipeline.py` — CLI Entry Point

```bash
uv run python -m ttsfeed.pipeline   # run for today (enrichment if API model, claude CLI, or codex CLI available)
```

`main(notify_fn: NotifyFn | None = None)` accepts an optional `notify_fn` callback matching `NotifyFn` from `ttsfeed.notify`. When provided, it is called instead of the built-in `send_notification`. Pass `None` (the default) to retain the standard Gmail SMTP behavior. This allows downstream repos to substitute their own notification logic (e.g. Resend-based dispatch) without modifying this package.

Calls `download_archive()` → `bytes_to_dataframe()` → `filter_recent_posts()` → `save_output(..., output_dir=RAW_OUTPUT_DIR, output_name="YYYY-MM-DD.json")` (always) → `build_complete_fn()` → `analyze_posts()` (if `complete` is not `None`) → `save_output(..., enrichment=enrichment, output_dir=ENRICHED_OUTPUT_DIR, output_name="YYYY-MM-DD.json")` (only if enrichment succeeds) → `notifier(reference_time, new_posts, enrichment)` → `_write_run_summary()` (always, writes `data/logs/YYYY-MM-DD.json`). Exits with code 1 on fetch errors. LLM failures are caught and logged as warnings, while the raw file remains intact. Email send errors are also caught and logged as warnings. Run `LOG_LEVEL` env var controls log verbosity (defaults to `INFO`).

---

## Dependencies

| Package    | Purpose                    |
|------------|----------------------------|
| `litellm`  | Unified LLM API client across providers |
| `pandas`   | DataFrame operations       |
| `python-dotenv` | Load local `.env` configuration at startup |
| `requests` | HTTP archive downloads     |

LLM enrichment can be forced with `LLM_PROVIDER` (`api`, `claude_code_cli`, `codex_cli`) or left as `auto` fallback. API mode uses LiteLLM; CLI modes use `claude` or `codex` via `subprocess` for local testing.

Dev: `pytest`, `pytest-mock`

---

## Resilience / Edge Cases

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

With enrichment (provider selected via `LLM_PROVIDER` or found by `auto` fallback):
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
    {"id": "123", "content": "We must secure our border!", "categories": ["Border & Immigration"], "is_reblog": false},
    {"id": "124", "content": "RT @someone: reposted text", "categories": [], "is_reblog": true},
    {"id": "125", "content": "", "categories": []}
  ]
}
```

Per-post `is_reblog` rules:
- Substantive post (has text, not RT): `"is_reblog": false`
- Reblog (starts with `"RT "`): `"is_reblog": true`
- Empty content (media/link): no `is_reblog` field

---

## Tests

Tests across 7 files. Run with:

```bash
pytest
```

### Coverage by Module

| File               | What's Covered                                                    |
|--------------------|-------------------------------------------------------------------|
| `test_notify.py`   | `send_notification`: SMTP call verified, correct subject/body, early-return when env vars missing |
| `test_analyze.py`  | `analyze_posts`: success path, empty posts, malformed JSON, missing keys, propagated exceptions; `_is_reblog`/`_has_content` helpers; pre-filter exclusion of reblogs/empty posts from LLM; all-non-substantive skips LLM |
| `test_config.py`   | `load_settings()`: defaults, TOML overrides (pipeline/llm/prompt), env var overrides, invalid JSON ignored, corrupt TOML falls back to defaults |
| `test_export.py`   | `_post_to_dict` (basic fields, list media, JSON-string media, NaN counts, None media), `save_output` (JSON structure, zero-post output, per-post enrichment categories) |
| `test_fetch.py`    | Download (success + failure), parsing (JSON), ID normalization, sorting, `filter_recent_posts` (recent/none/all/custom window, defaults to now) |
| `test_llm.py`      | `build_complete_fn`: explicit `LLM_PROVIDER` selection (`api`/`claude_code_cli`/`codex_cli`/`auto`), invalid provider handling, availability checks, and None fallback; `_call_llm_api`: success + propagated provider errors; `_call_claude_cli`: success path, non-zero exit code, missing structured_output key; `_call_codex_cli`: success + non-zero exit |
| `test_pipeline.py` | Two-phase save behavior (no LLM, LLM success, LLM failure) and fetch failure (exit 1) |

### Shared Fixtures (`conftest.py`)

| Fixture        | Description                                        |
|----------------|----------------------------------------------------|
| `sample_df`    | 3-row DataFrame with realistic schema (IDs 100–300) |
| `json_bytes`   | Binary JSON of `sample_df`                         |

All fetch tests mock HTTP calls; filter tests use timestamps relative to a fixed reference time.
