#!/usr/bin/env bash
# Lance Claude Code vers Ollama LAN (VM 110, modèle gemma4-claude).
# Équivalent Linux de scripts/claude-ollama-lan.ps1 (Windows).
#
# Usage :
#   bash infra/scripts/claude_ollama_lan.sh
#   bash infra/scripts/claude_ollama_lan.sh work .
#   bash infra/scripts/claude_ollama_lan.sh chat

set -euo pipefail

FRONT_IP="${LBG_LAN_HOST_FRONT:-192.168.0.110}"
OLLAMA_BASE="http://${FRONT_IP}:11434"
MODEL="${LBG_CLAUDE_OLLAMA_MODEL:-gemma4-claude}"

export ANTHROPIC_BASE_URL="${OLLAMA_BASE}"
export ANTHROPIC_AUTH_TOKEN="ollama"
export ANTHROPIC_API_KEY=""
export ANTHROPIC_MODEL="${MODEL}"
export ANTHROPIC_DEFAULT_SONNET_MODEL="${MODEL}"
export ANTHROPIC_DEFAULT_HAIKU_MODEL="${MODEL}"
export ANTHROPIC_DEFAULT_OPUS_MODEL="${MODEL}"
export CLAUDE_CODE_DISABLE_EXPERIMENTAL_BETAS="1"

if ! curl -sf --max-time 5 "${OLLAMA_BASE}/api/version" >/dev/null 2>&1; then
  echo "[claude_ollama_lan] ERREUR : Ollama injoignable sur ${OLLAMA_BASE}" >&2
  exit 1
fi

CLAUDE_BIN="${CLAUDE_BIN:-$HOME/.local/bin/claude}"
if [[ ! -x "${CLAUDE_BIN}" ]]; then
  echo "[claude_ollama_lan] ERREUR : Claude Code introuvable (${CLAUDE_BIN})" >&2
  exit 1
fi

if [[ $# -eq 0 ]]; then
  set -- work .
fi

exec "${CLAUDE_BIN}" --model "${MODEL}" "$@"
