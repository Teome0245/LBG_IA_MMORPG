#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
exec bash "${ROOT}/LBG_IA_MMO/infra/scripts/bootstrap_claude_on_core140.sh" "$@"
