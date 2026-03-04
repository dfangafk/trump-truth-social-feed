"""Tests for ttsfeed.llm provider selection and invocation helpers."""

import json
from pathlib import Path
import subprocess

import pytest

import ttsfeed.llm
from ttsfeed.llm import _CLI_OUTPUT_SCHEMA
from ttsfeed.llm import (
    _call_claude_cli,
    _call_codex_cli,
    _call_llm_api,
    build_complete_fn,
)


def _patch_llm_settings(mocker, provider, models):
    mocker.patch.object(ttsfeed.llm.settings.llm, "provider", provider)
    mocker.patch.object(ttsfeed.llm.settings.llm, "models", models)


def test_build_complete_fn_returns_api_fn_when_llm_models_env_set(mocker):
    _patch_llm_settings(mocker, "auto", ["openai/gpt-4o"])
    mock_which = mocker.patch("ttsfeed.llm.shutil.which", return_value=None)
    assert build_complete_fn() is _call_llm_api
    mock_which.assert_not_called()


def test_build_complete_fn_returns_api_fn_when_provider_explicitly_api(mocker):
    _patch_llm_settings(mocker, "api", ["openai/gpt-4o"])
    mock_which = mocker.patch("ttsfeed.llm.shutil.which", return_value=None)
    assert build_complete_fn() is _call_llm_api
    mock_which.assert_not_called()


def test_build_complete_fn_returns_none_when_provider_api_without_models(mocker):
    _patch_llm_settings(mocker, "api", [])
    mock_which = mocker.patch("ttsfeed.llm.shutil.which", return_value="/usr/bin/claude")
    assert build_complete_fn() is None
    mock_which.assert_not_called()


def test_build_complete_fn_returns_none_when_claude_not_on_path(mocker):
    _patch_llm_settings(mocker, "auto", [])
    mocker.patch("ttsfeed.llm.shutil.which", return_value=None)
    assert build_complete_fn() is None


def test_build_complete_fn_returns_callable_when_claude_on_path(mocker):
    _patch_llm_settings(mocker, "auto", [])
    mocker.patch("ttsfeed.llm.shutil.which", return_value="/usr/local/bin/claude")
    result = build_complete_fn()
    assert callable(result)


def test_build_complete_fn_returns_claude_fn_when_provider_explicitly_claude_code_cli(
    mocker,
):
    _patch_llm_settings(mocker, "claude_code_cli", [])
    mocker.patch("ttsfeed.llm.shutil.which", return_value="/usr/local/bin/claude")
    assert build_complete_fn() is _call_claude_cli


def test_build_complete_fn_returns_none_when_provider_claude_code_cli_unavailable(mocker):
    _patch_llm_settings(mocker, "claude_code_cli", [])
    mocker.patch("ttsfeed.llm.shutil.which", return_value=None)
    assert build_complete_fn() is None


def test_build_complete_fn_returns_codex_fn_when_codex_on_path(mocker):
    _patch_llm_settings(mocker, "auto", [])
    mocker.patch(
        "ttsfeed.llm.shutil.which",
        side_effect=lambda cmd: "/usr/local/bin/codex" if cmd == "codex" else None,
    )
    assert build_complete_fn() is _call_codex_cli


def test_build_complete_fn_returns_codex_fn_when_provider_explicitly_codex_cli(mocker):
    _patch_llm_settings(mocker, "codex_cli", [])
    mocker.patch(
        "ttsfeed.llm.shutil.which",
        side_effect=lambda cmd: "/usr/local/bin/codex" if cmd == "codex" else None,
    )
    assert build_complete_fn() is _call_codex_cli


def test_build_complete_fn_returns_none_when_provider_codex_cli_unavailable(mocker):
    _patch_llm_settings(mocker, "codex_cli", [])
    mocker.patch("ttsfeed.llm.shutil.which", return_value=None)
    assert build_complete_fn() is None


def test_build_complete_fn_returns_none_on_invalid_provider(mocker):
    _patch_llm_settings(mocker, "bogus", [])
    mock_which = mocker.patch("ttsfeed.llm.shutil.which", return_value="/usr/bin/claude")
    assert build_complete_fn() is None
    mock_which.assert_not_called()


def test_call_claude_cli_success(mocker):
    structured = {"summary": "Some summary", "posts": [{"id": "1", "categories": ["immigration"]}]}
    envelope = json.dumps({"structured_output": structured})
    mock_run = mocker.patch(
        "ttsfeed.llm.subprocess.run",
        return_value=subprocess.CompletedProcess(
            args=[], returncode=0, stdout=envelope, stderr=""
        ),
    )

    result = _call_claude_cli("test prompt")

    assert json.loads(result) == structured
    mock_run.assert_called_once()
    call_args = mock_run.call_args[0][0]
    assert call_args[0] == "claude"
    assert "-p" in call_args
    assert "test prompt" in call_args


def test_call_claude_cli_raises_on_nonzero_returncode(mocker):
    mocker.patch(
        "ttsfeed.llm.subprocess.run",
        return_value=subprocess.CompletedProcess(
            args=[], returncode=1, stdout="", stderr="something went wrong"
        ),
    )

    with pytest.raises(RuntimeError, match="claude CLI exited with code 1"):
        _call_claude_cli("test prompt")


def test_call_claude_cli_raises_when_structured_output_absent(mocker):
    envelope = json.dumps({"result": "unexpected shape"})
    mocker.patch(
        "ttsfeed.llm.subprocess.run",
        return_value=subprocess.CompletedProcess(
            args=[], returncode=0, stdout=envelope, stderr=""
        ),
    )

    with pytest.raises(RuntimeError, match="missing 'structured_output' key"):
        _call_claude_cli("test prompt")


def test_call_codex_cli_success(mocker):
    mock_unlink = mocker.patch("ttsfeed.llm.os.unlink")
    mock_run = mocker.patch(
        "ttsfeed.llm.subprocess.run",
        return_value=subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout='{"summary": "S", "posts": []}',
            stderr="",
        ),
    )

    result = _call_codex_cli("test prompt")

    assert result == '{"summary": "S", "posts": []}'
    mock_run.assert_called_once()
    call_args = mock_run.call_args[0][0]
    assert call_args[0] == "codex"
    assert call_args[1] == "exec"
    assert "--ephemeral" in call_args
    assert "--full-auto" in call_args
    assert "--output-schema" in call_args
    assert "test prompt" in call_args
    schema_path = call_args[call_args.index("--output-schema") + 1]
    assert json.loads(Path(schema_path).read_text(encoding="utf-8")) == json.loads(
        _CLI_OUTPUT_SCHEMA
    )
    mock_unlink.assert_called_once_with(schema_path)
    Path(schema_path).unlink(missing_ok=True)


def test_call_codex_cli_raises_on_nonzero_returncode(mocker):
    mocker.patch(
        "ttsfeed.llm.subprocess.run",
        return_value=subprocess.CompletedProcess(
            args=[], returncode=1, stdout="", stderr="something went wrong"
        ),
    )

    with pytest.raises(RuntimeError, match="codex CLI exited with code 1"):
        _call_codex_cli("test prompt")


def test_call_llm_api_success(mocker):
    mocker.patch.object(ttsfeed.llm.settings.llm, "models", ["openai/gpt-4o"])
    mock_completion = mocker.patch("ttsfeed.llm.completion")
    mock_completion.return_value = mocker.Mock(
        choices=[
            mocker.Mock(
                message=mocker.Mock(
                    content='{"summary":"Some summary","posts":[{"id":"1","categories":["economy"]}]}'
                )
            )
        ]
    )

    result = _call_llm_api("test prompt")

    assert result == '{"summary":"Some summary","posts":[{"id":"1","categories":["economy"]}]}'
    mock_completion.assert_called_once_with(
        model="openai/gpt-4o",
        messages=[{"role": "user", "content": "test prompt"}],
        response_format={"type": "json_object"},
        num_retries=3,
    )


def test_call_llm_api_raises_on_litellm_error(mocker):
    mocker.patch.object(ttsfeed.llm.settings.llm, "models", ["openai/gpt-4o"])
    mocker.patch("ttsfeed.llm.completion", side_effect=RuntimeError("api failed"))

    with pytest.raises(RuntimeError, match="api failed"):
        _call_llm_api("test prompt")


def test_call_llm_api_raises_when_models_empty(mocker):
    mocker.patch.object(ttsfeed.llm.settings.llm, "models", [])

    with pytest.raises(RuntimeError, match="LLM_MODELS is required"):
        _call_llm_api("test prompt")


def test_call_llm_api_falls_back_when_primary_fails(mocker):
    mocker.patch.object(ttsfeed.llm.settings.llm, "models", ["openai/gpt-4o", "gemini/gemini-2.5-flash"])
    fallback_content = '{"summary":"fallback summary","posts":[]}'
    mock_completion = mocker.patch(
        "ttsfeed.llm.completion",
        side_effect=[
            RuntimeError("primary down"),
            mocker.Mock(
                choices=[mocker.Mock(message=mocker.Mock(content=fallback_content))]
            ),
        ],
    )

    result = _call_llm_api("test prompt")

    assert result == fallback_content
    assert mock_completion.call_count == 2
    assert mock_completion.call_args_list[0][1]["model"] == "openai/gpt-4o"
    assert mock_completion.call_args_list[1][1]["model"] == "gemini/gemini-2.5-flash"


def test_call_llm_api_raises_when_all_models_fail(mocker):
    mocker.patch.object(ttsfeed.llm.settings.llm, "models", ["openai/gpt-4o", "gemini/gemini-2.5-flash"])
    mocker.patch(
        "ttsfeed.llm.completion",
        side_effect=[
            RuntimeError("primary down"),
            RuntimeError("fallback down"),
        ],
    )

    with pytest.raises(RuntimeError, match="fallback down"):
        _call_llm_api("test prompt")
