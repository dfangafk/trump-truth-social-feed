# trump-truth-social-feed

[![Daily Truth Social Feed](https://github.com/dfangafk/trump-truth-social-feed/actions/workflows/daily_ingest.yml/badge.svg)](https://github.com/dfangafk/trump-truth-social-feed/actions/workflows/daily_ingest.yml)

Daily LLM-enriched feed of Trump's Truth Social posts — automatically categorized, summarized, and emailed.

---

## What Is This?

Each day this pipeline pulls Trump's latest Truth Social posts, classifies each one into exactly one of 10 fixed categories, and generates a prose daily summary — all via LLM.

Built on top of [stiles/trump-truth-social-archive](https://github.com/stiles/trump-truth-social-archive), this repo adds the daily filtering, LLM enrichment, and email notification layer.

---

## Data Output

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
      "categories": ["Tariffs & Trade"],
      "is_reblog": false
    }
  ]
}
```

---

## LLM Enrichment

### Category taxonomy

Each post is assigned exactly one of these 10 categories:

- `Elections & Campaigns`
- `Tariffs & Trade`
- `Economy, Jobs & Inflation`
- `Taxes & Regulation`
- `Border & Immigration`
- `Crime & Public Safety`
- `Courts & Legal Proceedings`
- `Foreign Affairs & Defense`
- `Media & Public Narrative`
- `Other`

### Daily summary

The `summary.daily_summary` field is a 2-3 sentence prose overview synthesizing the major themes across all posts for that day.

---

## Configuration

Two files control the pipeline:

**`settings.toml`** — version-controlled behavior settings (provider, model, prompt, schedule, output flags, SMTP config):

```toml
[pipeline]
hours = 24
log_level = "INFO"
save_raw = false
save_enriched = false
save_logs = false

[fetch]
archive_url = "https://ix.cnn.io/data/truth-social/truth_archive.json"
timeout = 120

[notify]
timezone = "America/New_York"
smtp_host = "smtp.gmail.com"
smtp_port = 465
subject_template = "Trump Truth Social Feed — {date} ({count} new posts)"

[llm]
provider = "auto"    # auto | api | claude_code_cli | codex_cli
models = [
  "gemini/gemini-3-flash-preview",
  "gemini/gemini-2.5-flash",
]

[llm.api_kwargs]
num_retries = 3
```

**`.env`** — secrets only, never committed:

```bash
# API keys (required for LLM_PROVIDER=api or auto→api)
OPENAI_API_KEY=
ANTHROPIC_API_KEY=
GEMINI_API_KEY=

# Email notifications (leave blank to disable)
SENDER_GMAIL=           # must be a Gmail address
GMAIL_APP_PASSWORD=     # 16-char App Password from Google Account settings
RECEIVER_EMAIL=         # recipient address (any provider)
```

---

## How It Works

```
1. Download JSON archive from upstream CNN URL
        |
2. Parse to DataFrame, filter posts from last 24 hours
        |
3. Write raw JSON  ->  data/raw/YYYY-MM-DD.json        [always]
        |
4. Call LLM for categories + summary (if provider available)
        |
5. Write enriched JSON  ->  data/enriched/YYYY-MM-DD.json  [if enrichment succeeded]
        |
6. Send email digest via Gmail SMTP                    [if SMTP credentials set]
```

---

## Running Locally

**Prerequisites**: Python 3.12+, [`uv`](https://docs.astral.sh/uv/)

```bash
git clone https://github.com/dfangafk/trump-truth-social-feed.git
cd trump-truth-social-feed
uv sync
cp .env.example .env   # add API keys and/or email credentials
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

The `main()` entry point in `pipeline.py` accepts an optional `notify_fn` callback so downstream repos can substitute their own notification logic (e.g. Resend-based dispatch) without modifying this package.

---

## GitHub Actions

The workflow (`.github/workflows/daily_ingest.yml`) runs daily at **12:00 UTC** (7 AM ET) and can also be triggered manually via `workflow_dispatch`.

On each run it:
1. Installs dependencies with `uv`
2. Runs `ttsfeed.pipeline`
3. Commits any new files in `data/raw/`, `data/enriched/`, and `data/logs/` as `github-actions[bot]`

Secrets stored in the repository: `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `GEMINI_API_KEY`, `SENDER_GMAIL`, `GMAIL_APP_PASSWORD`, `RECEIVER_EMAIL`.

---

## Project Structure

```
trump-truth-social-feed/
├── ttsfeed/
│   ├── config.py        # Settings loader (settings.toml + .env), path constants
│   ├── fetch.py         # Download archive, parse to DataFrame, filter recent posts
│   ├── analyze.py       # LLM prompt construction, response parsing, EnrichResult
│   ├── llm.py           # LLM provider abstraction (API / Claude CLI / Codex CLI)
│   ├── export.py        # Serialize posts, write raw and enriched JSON output files
│   ├── notify.py        # Gmail SMTP email digest after enrichment
│   ├── pipeline.py      # Orchestrator: fetch -> enrich -> export -> notify -> log
│   └── templates/
│       ├── digest.html.jinja2
│       └── digest.txt.jinja2
├── tests/               # pytest tests (all external calls mocked)
├── data/
│   ├── raw/             # YYYY-MM-DD.json (no enrichment)
│   ├── enriched/        # YYYY-MM-DD.json (with categories + summary)
│   └── logs/            # YYYY-MM-DD.json (run metadata)
├── settings.toml        # Behavior config (version-controlled)
├── .env.example
└── .github/
    └── workflows/
        └── daily_ingest.yml
```

---

## Data Source & Dependency Risk

The upstream archive is hosted at [stiles/trump-truth-social-archive](https://github.com/stiles/trump-truth-social-archive) — a dataset of all public Trump Truth Social posts.

**Risk**: This pipeline is entirely dependent on the upstream data source. If the upstream repo is deleted, privatized, or restructured, ingestion will fail.

---

## Limitations

**Cron job delay** — GitHub Actions scheduled workflows can be delayed during high-load periods. If load is high enough, queued jobs may be dropped entirely.

**Gmail sender only** — The email digest uses Gmail SMTP (port 465, SSL) authenticated via an [App Password](https://myaccount.google.com/apppasswords) (requires 2-Step Verification). Other SMTP providers are not currently supported.
