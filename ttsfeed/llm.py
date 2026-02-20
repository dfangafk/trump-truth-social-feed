"""LLM provider abstraction for API and CLI-based enrichment providers."""

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


def _call_claude_cli(prompt: str) -> str:
    """Invoke `claude -p` in headless mode and return structured output as a JSON string.

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
    """Invoke `codex exec` in non-interactive mode and return JSON output string.

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


def build_complete_fn() -> Callable[[str], str] | None:
    """Return a completion callable backed by API or CLI provider.

    Returns:
        ``_call_llm_api`` if ``LLM_MODEL`` is set; otherwise
        ``_call_claude_cli`` if ``claude`` is on PATH; otherwise
        ``_call_codex_cli`` if ``codex`` is on PATH; ``None`` if no provider
        is available.
    """
    if os.getenv("LLM_MODEL"):
        logger.info("Selected enrichment provider: API (LLM_MODEL)")
        return _call_llm_api
    if shutil.which("claude") is not None:
        logger.info("Selected enrichment provider: Claude CLI")
        return _call_claude_cli
    if shutil.which("codex") is not None:
        logger.info("Selected enrichment provider: Codex CLI")
        return _call_codex_cli
    logger.info("No enrichment provider available")
    return None
