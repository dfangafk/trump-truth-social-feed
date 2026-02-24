# trump-truth-social-feed

[![Daily Truth Social Enrich](https://github.com/dfangafk/trump-truth-social-feed/actions/workflows/daily_ingest.yml/badge.svg)](https://github.com/dfangafk/trump-truth-social-feed/actions/workflows/daily_ingest.yml)

Daily LLM-enriched feed of Trump's Truth Social posts — automatically categorized and summarized.

---

## What Is This?

Each day this pipeline pulls Trump's latest Truth Social posts, classifies each one across a fixed 9-category taxonomy, and generates a prose daily summary — all via LLM. Results are committed directly to this repo so you can consume them without running any code.

Built on top of [stiles/trump-truth-social-archive](https://github.com/stiles/trump-truth-social-archive), which provides the raw Parquet/JSON archive maintained by CNN data journalist [@stiles](https://github.com/stiles). This repo adds the daily filtering and LLM enrichment layer.

Two output tiers are written each run:

| Path | Contents |
|------|----------|
| `data/enriched/YYYY-MM-DD.json` | Posts from the last 24 hours with per-post `categories` and a prose `daily_summary` — **primary data product** |
| `data/raw/YYYY-MM-DD.json` | Same posts, no LLM enrichment — written even when LLM is unavailable |

---

## Data Files

### Enriched output — `data/enriched/YYYY-MM-DD.json`

```json
{
  "as_of": "2026-02-21T00:52:42.326009+00:00",
  "window_hours": 24,
  "summary": {
    "total_posts_in_archive": 31623,
    "new_posts_count": 12,
    "daily_summary": "2-3 sentence prose overview of the day's posts..."
  },
  "new_posts": [
    {
      "id": "116105858701679073",
      "created_at": "2026-02-21T00:46:46.888Z",
      "content": "Post text...",
      "url": "https://truthsocial.com/@realDonaldTrump/116105858701679073",
      "media": [],
      "replies_count": 144,
      "reblogs_count": 375,
      "favourites_count": 1147,
      "categories": ["economy / trade", "legal / courts", "personal attacks"]
    }
  ]
}
```

### Raw output — `data/raw/YYYY-MM-DD.json`

Same structure as enriched, but `summary` omits `daily_summary` and each post has no `categories` field.

---

## LLM Enrichment

### Category taxonomy

Each post is assigned one or more of these 9 fixed categories:

- `immigration`
- `election integrity`
- `media criticism`
- `economy / trade`
- `foreign policy`
- `legal / courts`
- `endorsements`
- `personal attacks`
- `MAGA / rallies`

### Daily summary

The `summary.daily_summary` field is a 2-3 sentence prose overview synthesizing the major themes across all posts for that day.

### Environment variables

```bash
# .env.example
LLM_PROVIDER=auto          # auto | api | claude_code_cli | codex_cli
LLM_MODEL=                 # LiteLLM model string, e.g. openai/gpt-4o or claude-3-5-sonnet-20241022

ANTHROPIC_API_KEY=
OPENAI_API_KEY=
GEMINI_API_KEY=
```

Enrichment is **optional** — if no provider is available or the LLM call fails, the pipeline still writes raw output and exits cleanly.

---

## Data Source & Dependency Risk

The upstream archive is hosted at [stiles/trump-truth-social-archive](https://github.com/stiles/trump-truth-social-archive) — a dataset of all public Trump Truth Social posts.

**Risk**: For now, this pipeline is entirely dependent on the data source. If the upstream repo is deleted, privatized, or restructured, ingestion will fail.

---

## How It Works

```
1. Download Parquet archive from upstream CNN URL
        ↓ (fallback to JSON if Parquet fails)
2. Parse to DataFrame, filter posts from last 24 hours
        ↓
3. Write raw JSON → data/raw/YYYY-MM-DD.json
        ↓
4. Call LLM for categories + summary → write enriched JSON → data/enriched/YYYY-MM-DD.json
```

---

## Running Locally

**Prerequisites**: Python 3.12+, [`uv`](https://docs.astral.sh/uv/)

```bash
git clone https://github.com/dfangafk/trump-truth-social-feed.git
cd trump-truth-social-feed
uv sync
cp .env.example .env   # add LLM credentials
uv run python -m ttsfeed.pipeline
```

---

## Install as a Library

To use `ttsfeed` as a dependency in another Python project:

**With pip:**
```bash
pip install git+https://github.com/dfangafk/trump-truth-social-feed.git
```

**With uv:**
```bash
uv add git+https://github.com/dfangafk/trump-truth-social-feed.git
```

Or pin it in `pyproject.toml`:
```toml
dependencies = [
    "trump-truth-social-feed @ git+https://github.com/dfangafk/trump-truth-social-feed.git",
]
```

---

## GitHub Actions

The workflow (`.github/workflows/daily_ingest.yml`) runs daily at **23:30 UTC** and can also be triggered manually via `workflow_dispatch`.

On each run it:
1. Installs dependencies with `uv`
2. Runs `ttsfeed.pipeline`
3. Commits any new files in `data/raw/` and `data/enriched/` as `github-actions[bot]`

LLM credentials are stored as GitHub Actions secrets (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `GEMINI_API_KEY`) and repository variables (`LLM_PROVIDER`, `LLM_MODEL`).

---

## Limitations

**Cron job delay** — GitHub Actions scheduled workflows can be delayed during high-load periods (especially at the top of the hour). If load is high enough, queued jobs may be dropped entirely.

**Gmail sender only** — The email dispatch module supports Gmail as the sending account, authenticated via an [App Password](https://myaccount.google.com/apppasswords) (requires 2-Step Verification). Other SMTP providers are not currently supported.

---

## Project Structure

```
trump-truth-social-feed/
├── ttsfeed/
│   ├── config.py      # Constants, paths, category taxonomy
│   ├── fetch.py       # Download archive, parse to DataFrame
│   ├── analyze.py     # LLM prompt construction and response parsing
│   ├── llm.py         # LLM provider abstraction (API / CLI)
│   ├── export.py      # Write raw and enriched JSON output files
│   └── pipeline.py    # CLI entry point combining all steps
├── tests/             # pytest tests (all external calls mocked)
├── data/
│   ├── raw/           # YYYY-MM-DD.json (no enrichment)
│   └── enriched/      # YYYY-MM-DD.json (with categories + summary)
├── .env.example
└── .github/
    └── workflows/
        └── daily_ingest.yml
```
