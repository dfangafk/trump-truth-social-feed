"""Tests for ttsenrich.analyze."""

import json

import pytest

from ttsenrich.analyze import EnrichResult, analyze_posts


def _make_complete(response: str):
    """Return a mock complete callable that always returns *response*."""

    def complete(prompt: str) -> str:  # noqa: ARG001
        return response

    return complete


VALID_RESPONSE = json.dumps(
    {
        "summary": "Trump posted about immigration and trade policy.",
        "post_categories": {
            "1": ["immigration"],
            "2": ["economy / trade"],
        },
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
        "1": ["immigration"],
        "2": ["economy / trade"],
    }


def test_analyze_posts_empty_list():
    result = analyze_posts([], _make_complete(VALID_RESPONSE))

    assert result.daily_summary == ""
    assert result.post_categories == {}


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
