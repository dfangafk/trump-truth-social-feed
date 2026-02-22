"""Tests for ttsfeed.analyze."""

import json

import pytest

from ttsfeed.analyze import EnrichResult, _has_content, _is_reblog, analyze_posts


def _make_complete(response: str):
    """Return a mock complete callable that always returns *response*."""

    def complete(prompt: str) -> str:  # noqa: ARG001
        return response

    return complete


VALID_RESPONSE = json.dumps(
    {
        "summary": "Trump posted about immigration and trade policy.",
        "posts": [
            {"id": "1", "categories": ["Border & Immigration"]},
            {"id": "2", "categories": ["Tariffs & Trade"]},
        ],
    }
)

SAMPLE_POSTS = [
    {"id": "1", "content": "We must secure our border!"},
    {"id": "2", "content": "Tariffs are great for America."},
]


def test_analyze_posts_success():
    result = analyze_posts(SAMPLE_POSTS, _make_complete(VALID_RESPONSE))

    assert isinstance(result, EnrichResult)
    assert result.daily_summary == "Trump posted about immigration and trade policy."
    assert result.post_categories == {
        "1": ["Border & Immigration"],
        "2": ["Tariffs & Trade"],
    }
    assert result.post_is_reblog == {"1": False, "2": False}


def test_analyze_posts_empty_list():
    result = analyze_posts([], _make_complete(VALID_RESPONSE))

    assert result.daily_summary == ""
    assert result.post_categories == {}
    assert result.post_is_reblog == {}


def test_analyze_posts_malformed_json_raises():
    with pytest.raises(ValueError, match="non-JSON"):
        analyze_posts(SAMPLE_POSTS, _make_complete("this is not json"))


def test_analyze_posts_missing_keys_raises():
    bad_response = json.dumps({"result": "something"})
    with pytest.raises(ValueError, match="missing required keys"):
        analyze_posts(SAMPLE_POSTS, _make_complete(bad_response))


def test_analyze_posts_propagates_complete_exception():
    def failing_complete(prompt: str) -> str:
        raise RuntimeError("API call failed")

    with pytest.raises(RuntimeError, match="API call failed"):
        analyze_posts(SAMPLE_POSTS, failing_complete)


# --- _is_reblog ---


def test_is_reblog_detects_rt_prefix():
    assert _is_reblog({"content": "RT @someone: something"}) is True


def test_is_reblog_false_for_normal_post():
    assert _is_reblog({"content": "Normal post"}) is False


def test_is_reblog_false_for_empty_content():
    assert _is_reblog({"content": ""}) is False


def test_is_reblog_false_for_missing_content():
    assert _is_reblog({}) is False


# --- _has_content ---


def test_has_content_true_for_text():
    assert _has_content({"content": "Some text"}) is True


def test_has_content_false_for_empty():
    assert _has_content({"content": ""}) is False


def test_has_content_false_for_whitespace():
    assert _has_content({"content": "   "}) is False


def test_has_content_false_for_missing():
    assert _has_content({}) is False


# --- pre-filter behavior ---


def test_reblog_and_empty_excluded_from_llm():
    """Reblog and empty-content posts must not be included in the LLM prompt."""
    captured_prompts: list[str] = []

    def capture_complete(prompt: str) -> str:
        captured_prompts.append(prompt)
        return json.dumps({
            "summary": "Border post only.",
            "posts": [{"id": "1", "categories": ["Border & Immigration"]}],
        })

    posts = [
        {"id": "1", "content": "We must secure our border!"},
        {"id": "2", "content": "RT @someone: something"},  # reblog
        {"id": "3", "content": ""},  # empty
    ]
    result = analyze_posts(posts, capture_complete)

    # LLM was called exactly once
    assert len(captured_prompts) == 1
    prompt = captured_prompts[0]
    # Only the substantive post appears in the prompt
    assert "id=1" in prompt
    assert "id=2" not in prompt
    assert "id=3" not in prompt

    # Reblog is flagged
    assert result.post_is_reblog["2"] is True
    # Substantive post is flagged as not reblog
    assert result.post_is_reblog["1"] is False
    # Empty post has no is_reblog entry
    assert "3" not in result.post_is_reblog

    # Categories
    assert result.post_categories["1"] == ["Border & Immigration"]
    assert result.post_categories["2"] == []
    assert result.post_categories["3"] == []


def test_all_reblogs_or_empty_skips_llm():
    """When all posts are non-substantive, the LLM should not be called."""
    call_count = 0

    def counting_complete(prompt: str) -> str:  # noqa: ARG001
        nonlocal call_count
        call_count += 1
        return "{}"

    posts = [
        {"id": "1", "content": "RT @x: something"},
        {"id": "2", "content": ""},
    ]
    result = analyze_posts(posts, counting_complete)

    assert call_count == 0
    assert result.daily_summary == ""
    assert result.post_categories == {"1": [], "2": []}
    assert result.post_is_reblog == {"1": True}
