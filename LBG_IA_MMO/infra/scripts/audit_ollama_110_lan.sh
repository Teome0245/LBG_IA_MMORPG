#!/usr/bin/env bash
# Audit Ollama VM 110 — inventaire vs config LBG (LAN).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
export OLLAMA_BASE_URL="${OLLAMA_BASE_URL:-http://192.168.0.110:11434}"
export LBG_DIALOGUE_LLM_MODEL="${LBG_DIALOGUE_LLM_MODEL:-gemma4:26b}"
export LBG_REASON_MODEL_FORGE="${LBG_REASON_MODEL_FORGE:-gemma4:e2b}"
cd "${ROOT}/orchestrator"
PYTHONPATH=.:../agents/src ../orchestrator/.venv/bin/python -c "
from team.ollama_audit import audit_ollama_lan
import json
print(json.dumps(audit_ollama_lan(), ensure_ascii=False, indent=2))
"
