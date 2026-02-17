# Truth Social Scraper — Research Findings

*Date: February 16, 2026*

## Goal

Fetch Trump's posts from Truth Social on a daily basis programmatically.

---

## Truth Social API

Truth Social is a Mastodon fork and exposes Mastodon-compatible API endpoints.

- **Endpoint**: `GET https://truthsocial.com/api/v1/accounts/{account_id}/statuses`
- **Trump's account ID**: `107780257626128497`
- **Account lookup**: `GET /api/v1/accounts/lookup?acct=realDonaldTrump`
- **Authentication**: Not required for Trump's public posts (prominent accounts are public)
- **Pagination**: `since_id`, `max_id`, `min_id` params; `limit` max 40 per page
- **Content format**: `content` field returns HTML (needs stripping for plain text)
- **Rate limits**: Not publicly documented

### API Response Fields (per Mastodon Status entity)

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Post ID (cast from integer) |
| `created_at` | string | ISO 8601 timestamp |
| `content` | string | HTML-formatted post text |
| `url` | string | Direct link to post |
| `visibility` | string | `public`, `unlisted`, etc. |
| `language` | string | e.g. `en` |
| `sensitive` | boolean | Content warning flag |
| `spoiler_text` | string | Content warning text |
| `in_reply_to_id` | string/null | Parent post ID if reply |
| `replies_count` | integer | Number of replies |
| `reblogs_count` | integer | Number of re-truths |
| `favourites_count` | integer | Number of likes |
| `media_attachments` | array | Images/videos with URLs |
| `mentions` | array | Tagged accounts |
| `tags` | array | Hashtags |
| `card` | object/null | Link preview |
| `reblog` | object/null | Full re-truthed post |
| `account` | object | Author info (username, followers, etc.) |

---

## Key Finding: Cloudflare Blocks Direct API Access

**The Truth Social API is behind Cloudflare and returns HTTP 403 for programmatic requests.**

Tested via curl — returns "Sorry, you have been blocked" Cloudflare page. This applies regardless of User-Agent headers. Cloudflare uses:
- TLS fingerprinting
- JavaScript challenges
- Behavioral analysis
- IP reputation scoring

Simple header spoofing is **not sufficient** to bypass.

---

## Approaches Evaluated

### 1. Direct API with `requests` (Python)
- **Status**: Does NOT work
- **Reason**: Cloudflare 403 block
- **Cost**: Free
- **Verdict**: Not viable

### 2. ScrapeOps Proxy
- **Status**: Works (proven by trump-truth-social-archive project)
- **How**: Routes requests through ScrapeOps proxy pool with `bypass=cloudflare_level_1`
- **Cost**: Free tier — 1,000 requests/month (plenty for daily fetching)
- **Complexity**: Low — just add API key to request URL
- **Verdict**: Best self-reliant option

### 3. Existing Public Archive (CNN/Matt Stiles)
- **URL**: `https://ix.cnn.io/data/truth-social/truth_archive.json` (also `.csv`, `.parquet`)
- **Status**: Works — confirmed live with today's posts (Feb 16, 2026)
- **Update frequency**: Every 5 minutes
- **Source project**: [stiles/trump-truth-social-archive](https://github.com/stiles/trump-truth-social-archive)
- **Maintainer**: Matt Stiles (journalist/data editor at CNN)
- **Note**: The GitHub Actions workflow was disabled Oct 26, 2025. The archive continues updating via CNN's internal infrastructure.
- **Data fields**: `id`, `created_at`, `content` (plain text), `url`, `media` (array of URLs), `replies_count`, `reblogs_count`, `favourites_count`
- **Cost**: Free
- **Risk**: Depends on third-party continuing to maintain it
- **Verdict**: Simplest option but not self-reliant

### 4. Browser Automation (nodriver / Playwright)
- **Status**: Partially works
- **How**: Runs a real Chrome browser via DevTools Protocol
- **Limitation**: Rate-limited by Cloudflare after ~40 posts per session
- **Workaround**: 20-second pauses per 100 posts, rotating proxies
- **Cost**: Free (but needs Chrome installed)
- **Complexity**: High — requires Chrome, harder in GitHub Actions (needs xvfb)
- **Note**: `puppeteer-extra-stealth` is deprecated as of Feb 2025. Use `nodriver` instead.
- **Verdict**: Complex, fragile, not recommended for this use case

### 5. AI Agents (Claude Computer Use / ChatGPT Operator / browser-use)
- **Status**: Technically possible but overkill
- **How**: LLM controls a browser to navigate and extract data
- **Cost**: $0.10–0.50 per run (LLM API costs for screenshots + reasoning)
- **Complexity**: High
- **Advantage**: Can adapt to UI changes automatically
- **Disadvantage**: 10-100x more expensive than proxy approach for structured data
- **Verdict**: Only makes sense if API/proxy approaches fail AND website changes frequently

### 6. Third-Party Services (Bright Data, Apify)
- **Status**: Works
- **Cost**: Paid — Apify ~$0.55-0.65 per 1,000 results; Bright Data varies
- **Complexity**: Low
- **Verdict**: Viable but unnecessary given free alternatives

---

## Comparison Summary

| Approach | Works? | Cost | Complexity | Self-Reliant? |
|----------|--------|------|------------|---------------|
| Direct API | No | Free | Low | Yes |
| ScrapeOps proxy | Yes | Free (1K req/mo) | Low | Yes |
| CNN archive | Yes | Free | Lowest | No |
| nodriver/Playwright | Partial | Free | High | Yes |
| AI agents | Yes | $3-15/mo | High | Yes |
| Bright Data/Apify | Yes | Paid | Low | Yes |

---

## Existing Open-Source Projects

| Project | Language | Approach | Status |
|---------|----------|----------|--------|
| [stiles/trump-truth-social-archive](https://github.com/stiles/trump-truth-social-archive) | Python | ScrapeOps proxy | GitHub Actions disabled; CNN archive still live |
| [stanfordio/truthbrush](https://github.com/stanfordio/truthbrush) | Python | OAuth auth + direct API | Hits Cloudflare rate limits; maintainers noted "bypassing cloudflare is out of scope" |
| [favstats/untruthr](https://github.com/favstats/untruthr) | R | Scraper | Community project |

---

## Truth Social API Quirks vs Standard Mastodon

- Forked from Mastodon **3.4.1** (significantly outdated)
- **No official API documentation** or developer portal
- RSS feeds are intentionally empty (unlike Mastodon)
- Custom endpoints exist (`/api/v1/truth/...`, `/api/v4/truth/...`)
- Only prominent accounts (Trump, Vance) are publicly accessible without auth
- Other users' posts require OAuth authentication
- Post sensitivity/privacy can be changed after creation (not in standard Mastodon)

---

## Recommended Next Steps

1. **Quickest start**: Fetch from CNN archive (`ix.cnn.io`) — zero setup, free, live data
2. **Self-reliant**: Set up ScrapeOps proxy pipeline — free tier, same approach the archive uses
3. **Future-proof**: Build with ScrapeOps as primary, CNN archive as fallback
