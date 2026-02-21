# Email Dispatch System — Design Discussion

## Overview

A system to send daily Truth Social post digests to subscribed email addresses.

---

## Components Needed

### Data & Storage
- Subscriber list (email addresses, preferences, opt-in/out status)
- Unsubscribe tracking (CAN-SPAM/GDPR compliance)

### Email Composition
- HTML/plain-text email template rendering the daily JSON output
- Optional personalization (e.g., subscriber name)

### Dispatch Mechanism
- Transactional email provider (SendGrid, AWS SES, Postmark, etc.) — preferred over raw SMTP for deliverability and bounce handling
- Batching/rate limiting for large subscriber lists

### Scheduling & Orchestration
- Triggered after the existing pipeline succeeds and produces the daily JSON
- Idempotency to prevent double-sends on workflow retries

### Delivery Health
- Bounce handling (hard bounces auto-remove addresses)
- Unsubscribe link in every email (legally required)
- Optional open/click tracking via email provider

### Operational Concerns
- API keys stored as GitHub Actions secrets
- Logging and alerting for send failures
- Subscription management (signup form, API endpoint, or manual process)

---

## Repo Architecture

### Option A: Build within this repo
- Simpler, no cross-repo dependency management
- Suitable for small/personal projects
- Mixes two concerns: data pipeline + subscriber management

### Option B: New repo importing this one as a library
- Clean separation of concerns
- Different deployment models for each system
- `ttsenrich` package API is already well-defined for this

### Option C: New repo consuming JSON output (no library dependency)
- The pipeline already commits daily JSON to `data/output/`
- New system reads those files directly (git checkout, raw GitHub URL, etc.)
- Fully decouples the two systems — no library import needed
- Best fit if the new system only needs to *consume* output, not run the pipeline itself

---

## Deployment Options

### GitHub Actions + External Database
- Dispatch runs as a cron job in a new repo's Actions workflow
- Database is an external hosted service
- **No live web endpoint** — subscription management must be handled manually or separately
- Best if you don't need a signup form

### Serverless Functions (AWS Lambda, Vercel, Cloudflare Workers)
- Functions handle dispatch trigger and signup/unsubscribe endpoints
- Still requires an external database
- Cheap at low scale; more wiring required

### PaaS (Railway, Render, Fly.io)
- Web service + managed database on one platform
- Easy to add a live signup/unsubscribe endpoint
- Low ops overhead

### Managed Platforms (Supabase, Firebase)
- Database, auth, and API provided out of the box
- Fastest path to a working subscriber list + signup endpoint
- Some vendor lock-in

---

## Pricing Summary (approximate, verify before committing)

| Option | Free Tier | Paid |
|---|---|---|
| GitHub Actions (public repo) | Unlimited | — |
| Neon (Postgres) | 0.5 GB, 1 project | ~$19/month |
| Supabase (Postgres) | 500 MB DB, 50K MAU, 5 GB egress | ~$25/month |
| Turso (SQLite) | 9 GB, 500 DBs | ~$29/month |
| Vercel Functions | 100K invocations/month | ~$20/month |
| Cloudflare Workers | 100K requests/day | ~$5/month |
| AWS Lambda | 1M requests/month | Pay-per-use |
| Railway | ~$5 credit/month | $5/month hobby |
| Render | Free (sleeps on inactivity) | $7/month always-on |
| Fly.io | Small free allowance | ~$2–5/month |
| Firebase | Generous free (Spark plan) | Pay-as-you-go (Blaze) |

---

## Recommended Starting Point

For a small subscriber list with one email per day:

- **$0/month**: GitHub Actions (free, public repo) + Supabase free tier
  - 500 MB database is far more than needed for a subscriber table
  - No live signup endpoint without additional hosting

- **~$5/month**: Railway + Postgres
  - Adds a live web endpoint for signups/unsubscribes
  - Single platform for app + database
