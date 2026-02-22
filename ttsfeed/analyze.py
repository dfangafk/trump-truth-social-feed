"""LLM enrichment: summarize posts and assign categories."""

import json
import logging
from collections.abc import Callable
from dataclasses import dataclass, field

from ttsfeed.config import POST_CATEGORIES

logger = logging.getLogger(__name__)

_PROMPT_TEMPLATE = """\
You are analyzing Trump's Truth Social posts for a daily briefing.

Posts ({n} total):
{numbered_posts}

Select all applicable categories from this fixed list:
{categories}

Respond with valid JSON only, no markdown:
{{"summary": "<2-3 sentence summary of key themes>", "post_categories": {{"<post id>": ["<matching categories>"]}}}}"""


@dataclass
class EnrichResult:
    """Result of LLM enrichment of a set of posts."""

    daily_summary: str
    post_categories: dict[str, list[str]] = field(default_factory=dict)


def analyze_posts(posts: list[dict], complete: Callable[[str], str]) -> EnrichResult:
    """Send all posts to the LLM and return a summary and per-post categories.

    Args:
        posts: List of post dicts (must contain a ``content`` key).
        complete: Callable that accepts a prompt string and returns the LLM response.

    Returns:
        EnrichResult with ``daily_summary`` and ``post_categories``.

    Raises:
        ValueError: If the LLM response cannot be parsed as valid JSON with expected keys.
        Exception: Any exception raised by ``complete`` is propagated to the caller.
    """
    if not posts:
        return EnrichResult(daily_summary="", post_categories={})

    numbered_posts = "\n".join(
        f"{i + 1}. [id={p.get('id', '')}] {p.get('content', '')}"
        for i, p in enumerate(posts)
    )
    prompt = _PROMPT_TEMPLATE.format(
        n=len(posts),
        numbered_posts=numbered_posts,
        categories=", ".join(POST_CATEGORIES),
    )

    raw = complete(prompt)

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"LLM returned non-JSON response: {raw!r}") from exc

    if "summary" not in parsed or "post_categories" not in parsed:
        raise ValueError(
            "LLM response missing required keys 'summary'/'post_categories': "
            f"{parsed!r}"
        )

    return EnrichResult(
        daily_summary=str(parsed["summary"]),
        post_categories=dict(parsed["post_categories"]),
    )
