"""LLM enrichment: summarize posts and assign categories."""

import json
import logging
from collections.abc import Callable
from dataclasses import dataclass, field

from ttsfeed.config import MAX_TAGS_PER_POST, POST_TAGS

POST_TAG_LINES: str = "\n".join(f"  - {name}: {desc}" for name, desc in POST_TAGS.items())

logger = logging.getLogger(__name__)

ENRICHMENT_SCHEMA: str = json.dumps(
    {
        "type": "object",
        "properties": {
            "summary": {"type": "string"},
            "posts": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string"},
                        "categories": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["id", "categories"],
                },
            },
        },
        "required": ["summary", "posts"],
    }
)

_PROMPT_TEMPLATE = """\
You are analyzing Trump's Truth Social posts for a daily briefing.

Substantive posts ({n} total):
{numbered_posts}

Assign each post up to {max_tags} categories from this list. Always assign at least one category; use "Other" if no specific category fits:
{category_lines}

Respond with valid JSON only, no markdown:
{{"summary": "<2-3 sentence daily overview>", "posts": [{{"id": "<post id>", "categories": ["<category names>"]}}]}}"""


def _is_reblog(post: dict) -> bool:
    """Return True if the post is a reblog (starts with 'RT ')."""
    return post.get("content", "").startswith("RT ")


def _has_content(post: dict) -> bool:
    """Return True if the post has non-empty text content."""
    return post.get("content", "").strip() != ""


@dataclass
class EnrichResult:
    """Result of LLM enrichment of a set of posts."""

    daily_summary: str
    post_categories: dict[str, list[str]] = field(default_factory=dict)
    post_is_reblog: dict[str, bool] = field(default_factory=dict)


def analyze_posts(posts: list[dict], complete: Callable[[str], str]) -> EnrichResult:
    """Pre-filter posts then send substantive posts to the LLM for categorization.

    Empty-content posts (media/link) and reblogs (RT prefix) are classified
    programmatically without an LLM call. Only substantive posts are batched
    into a single LLM call.

    Args:
        posts: List of post dicts (must contain ``id`` and ``content`` keys).
        complete: Callable that accepts a prompt string and returns the LLM response.

    Returns:
        EnrichResult with ``daily_summary``, ``post_categories``, and ``post_is_reblog``.

    Raises:
        ValueError: If the LLM response cannot be parsed as valid JSON with expected keys.
        Exception: Any exception raised by ``complete`` is propagated to the caller.
    """
    if not posts:
        return EnrichResult(daily_summary="", post_categories={}, post_is_reblog={})

    # Pre-classify posts: skip empty and reblogs; batch substantive ones for LLM.
    substantive: list[dict] = []
    post_categories: dict[str, list[str]] = {}
    post_is_reblog: dict[str, bool] = {}

    for post in posts:
        post_id = str(post.get("id", ""))
        if not _has_content(post):
            # Empty content — media/link post; no is_reblog entry
            post_categories[post_id] = []
        elif _is_reblog(post):
            # Reblog/RT — mark as reblog, skip LLM
            post_categories[post_id] = []
            post_is_reblog[post_id] = True
        else:
            # Substantive — send to LLM
            substantive.append(post)
            post_is_reblog[post_id] = False

    logger.info("Analyzing %d posts (%d substantive)", len(posts), len(substantive))

    if not substantive:
        return EnrichResult(
            daily_summary="",
            post_categories=post_categories,
            post_is_reblog=post_is_reblog,
        )

    numbered_posts = "\n".join(
        f"{i + 1}. [id={p.get('id', '')}] {p.get('content', '')}"
        for i, p in enumerate(substantive)
    )
    prompt = _PROMPT_TEMPLATE.format(
        n=len(substantive),
        numbered_posts=numbered_posts,
        max_tags=MAX_TAGS_PER_POST,
        category_lines=POST_TAG_LINES,
    )

    raw = complete(prompt)
    logger.debug("LLM raw response: %s", raw)

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"LLM returned non-JSON response: {raw!r}") from exc

    if "summary" not in parsed or "posts" not in parsed:
        raise ValueError(
            "LLM response missing required keys 'summary'/'posts': "
            f"{parsed!r}"
        )

    logger.info(
        "LLM response parsed: %d categories, summary %d chars",
        len(parsed["posts"]),
        len(str(parsed["summary"])),
    )

    # Merge LLM per-post categories with pre-classified results
    for entry in parsed["posts"]:
        pid = str(entry.get("id", ""))
        post_categories[pid] = list(entry.get("categories", []))

    return EnrichResult(
        daily_summary=str(parsed["summary"]),
        post_categories=post_categories,
        post_is_reblog=post_is_reblog,
    )
