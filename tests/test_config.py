"""Tests for ttsfeed.config — Settings defaults and env var overrides."""

import pytest

from ttsfeed.config import (
    FetchSettings,
    LLMSettings,
    PathSettings,
    PipelineSettings,
    PromptSettings,
    Settings,
)


# --- Defaults ---


def test_settings_defaults():
    s = Settings()
    assert s.pipeline.hours == 24
    assert s.pipeline.log_level == "INFO"
    assert s.pipeline.enable_llm is True
    assert s.pipeline.enable_notify is True
    assert s.llm.provider == "auto"
    assert s.fetch.timeout == 120
    assert s.notify.smtp_port == 465


# --- Pipeline env var overrides ---


def test_pipeline_override_via_env(monkeypatch):
    monkeypatch.setenv("PIPELINE__HOURS", "48")
    monkeypatch.setenv("PIPELINE__LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("PIPELINE__ENABLE_LLM", "false")

    s = Settings()
    assert s.pipeline.hours == 48
    assert s.pipeline.log_level == "DEBUG"
    assert s.pipeline.enable_llm is False


# --- LLM env var overrides ---


def test_llm_override_via_env(monkeypatch):
    monkeypatch.setenv("LLM__PROVIDER", "api")

    s = Settings()
    assert s.llm.provider == "api"


# --- Prompt env var overrides ---


def test_prompt_override_via_env(monkeypatch):
    monkeypatch.setenv("PROMPT__TEMPLATE", "custom template {n} {numbered_posts} {categories}")

    s = Settings()
    assert s.prompt.template == "custom template {n} {numbered_posts} {categories}"


# --- Nested delimiter support ---


def test_nested_delimiter_fetch(monkeypatch):
    monkeypatch.setenv("FETCH__TIMEOUT", "30")
    monkeypatch.setenv("FETCH__USER_AGENT", "test-agent/1.0")

    s = Settings()
    assert s.fetch.timeout == 30
    assert s.fetch.user_agent == "test-agent/1.0"


def test_nested_delimiter_notify(monkeypatch):
    monkeypatch.setenv("NOTIFY__SMTP_PORT", "587")
    monkeypatch.setenv("NOTIFY__TIMEZONE", "UTC")

    s = Settings()
    assert s.notify.smtp_port == 587
    assert s.notify.timezone == "UTC"


# --- Secret fields ---


def test_secret_override_via_env(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key-123")

    s = Settings()
    assert s.gemini_api_key == "test-key-123"
