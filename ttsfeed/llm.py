"""LLM provider abstraction for API and local-testing CLI enrichment providers."""

import json
import logging
import os
import shutil
import subprocess
import tempfile
from collections.abc import Callable

from litellm import completion

logger = logging.getLogger(__name__)

_ENRICHMENT_SCHEMA: str = json.dumps(
    {
        "type": "object",
        "properties": {
            "summary": {"type": "string"},
            "post_categories": {
                "type": "object",
                "additionalProperties": {
                    "type": "array",
                    "items": {"type": "string"},
                },
            },
        },
        "required": ["summary", "post_categories"],
    }
)


def _call_llm_api(prompt: str) -> str:
    """Invoke an LLM provider API through LiteLLM and return JSON output string.

    The model is resolved from ``LLM_MODEL`` environment variable and provider
    credentials are handled by LiteLLM using provider-specific environment keys
    (for example: ``ANTHROPIC_API_KEY`` or ``OPENAI_API_KEY``).

    Args:
        prompt: The prompt to send to the configured model.

    Returns:
        JSON string containing ``summary`` and ``post_categories`` keys.
    """
    model = os.environ["LLM_MODEL"]
    logger.info("Using LLM API model: %s", model)
    response = completion(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
    )
    return response.choices[0].message.content


def _call_claude_cli(prompt: str) -> str:
    """Invoke `claude -p` in headless mode for local testing and return structured output as JSON.

    Args:
        prompt: The prompt to send to Claude.

    Returns:
        JSON string containing ``summary`` and ``post_categories`` keys.

    Raises:
        RuntimeError: If the subprocess exits with a non-zero code or if
            ``structured_output`` is absent from the response envelope.
    """
    result = subprocess.run(
        [
            "claude",
            "-p",
            prompt,
            "--output-format",
            "json",
            "--json-schema",
            _ENRICHMENT_SCHEMA,
            "--no-session-persistence",
        ],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        raise RuntimeError(
            f"claude CLI exited with code {result.returncode}: {result.stderr.strip()}"
        )

    response = json.loads(result.stdout)

    if "structured_output" not in response:
        raise RuntimeError(
            f"claude CLI response missing 'structured_output' key: {response!r}"
        )

    return json.dumps(response["structured_output"])


def _call_codex_cli(prompt: str) -> str:
    """Invoke `codex exec` in non-interactive mode for local testing and return a JSON output string.

    Args:
        prompt: The prompt to send to Codex.

    Returns:
        JSON string containing ``summary`` and ``post_categories`` keys.

    Raises:
        RuntimeError: If the subprocess exits with a non-zero code.
    """
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        suffix=".json",
        delete=False,
    ) as schema_file:
        schema_file.write(_ENRICHMENT_SCHEMA)
        schema_path = schema_file.name

    try:
        result = subprocess.run(
            [
                "codex",
                "exec",
                "--ephemeral",
                "--full-auto",
                "--output-schema",
                schema_path,
                prompt,
            ],
            capture_output=True,
            text=True,
        )
    finally:
        os.unlink(schema_path)

    if result.returncode != 0:
        raise RuntimeError(
            f"codex CLI exited with code {result.returncode}: {result.stderr.strip()}"
        )

    return result.stdout.strip()


def build_complete_fn() -> Callable[[str], str] | None:
    """Return a completion callable backed by API or CLI provider.

    Set ``LLM_PROVIDER`` to explicitly choose a provider:
    ``api``, ``claude``, ``codex``, or ``auto`` (default).

    Returns:
        ``_call_llm_api``/``_call_claude_cli``/``_call_codex_cli`` based on
        ``LLM_PROVIDER`` when explicitly set and available; otherwise, in
        ``auto`` mode, ``_call_llm_api`` if ``LLM_MODEL`` is set (primary
        runtime path), else ``_call_claude_cli`` if ``claude`` is on PATH
        (local testing), else ``_call_codex_cli`` if ``codex`` is on PATH
        (local testing), else ``None``.
    """
    provider = (os.getenv("LLM_PROVIDER", "auto") or "auto").strip().lower()
    if provider not in {"api", "claude", "codex", "auto"}:
        logger.warning(
            "Invalid %s value '%s'; expected one of: api, claude, codex, auto",
            "LLM_PROVIDER",
            provider,
        )
        return None

    if provider in {"api", "auto"} and os.getenv("LLM_MODEL"):
        logger.info("Selected enrichment provider: API (LLM_MODEL)")
        return _call_llm_api

    if provider in {"claude", "auto"} and shutil.which("claude") is not None:
        logger.info("Selected enrichment provider: Claude CLI")
        return _call_claude_cli

    if provider in {"codex", "auto"} and shutil.which("codex") is not None:
        logger.info("Selected enrichment provider: Codex CLI")
        return _call_codex_cli

    if provider != "auto":
        logger.warning("Requested enrichment provider '%s' is not available", provider)
    else:
        logger.info("No enrichment provider available")
    return None
