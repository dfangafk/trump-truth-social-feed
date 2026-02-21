#!/usr/bin/env bash
set -euo pipefail

# Parse a variable from .env without sourcing the file
get_env_var() {
  local key="$1"
  grep -E "^${key}=" .env | head -1 | cut -d'=' -f2-
}

echo "Syncing .env → GitHub repo secrets and variables..."

# --- Secrets (sensitive keys) ---
for secret in OPENAI_API_KEY ANTHROPIC_API_KEY GEMINI_API_KEY; do
  value=$(get_env_var "$secret")
  if [[ -n "$value" ]]; then
    gh secret set "$secret" --body "$value"
    echo "  secret set: $secret"
  else
    echo "  skipped (empty): $secret"
  fi
done

# --- Variables (non-sensitive config) ---
for var in LLM_PROVIDER LLM_MODEL; do
  value=$(get_env_var "$var")
  if [[ -n "$value" ]]; then
    gh variable set "$var" --body "$value"
    echo "  variable set: $var"
  else
    echo "  skipped (empty): $var"
  fi
done

echo "Done."
