#!/usr/bin/env bash
# Vérifie l'alignement Claude Code : poste dev (WSL/Windows repo) ↔ VM 140 ↔ Ollama 110.
#
# Usage (depuis LBG_IA_MMO/) :
#   bash infra/scripts/verify_claude_alignment.sh
#
# Variables :
#   LBG_LAN_HOST_CORE   (défaut 192.168.0.140)
#   LBG_LAN_HOST_FRONT  (défaut 192.168.0.110)
#   LBG_VM_USER         (défaut lbg)
#   LBG_VM_DIR          (défaut /opt/LBG_IA_MMO)
#   LBG_CLAUDE_OLLAMA_MODEL (défaut gemma4-claude)
#   LBG_WINDOWS_REPO    chemin Windows ex. /mnt/c/Users/.../LBG_IA_MMORPG (auto si trouvé)
#   LBG_SSH_IDENTITY    clé SSH optionnelle

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
REPO_ROOT="$(cd "${ROOT}/.." && pwd)"
CORE_HOST="${LBG_LAN_HOST_CORE:-192.168.0.140}"
FRONT_HOST="${LBG_LAN_HOST_FRONT:-192.168.0.110}"
VM_USER="${LBG_VM_USER:-lbg}"
REMOTE_DIR="${LBG_VM_DIR:-/opt/LBG_IA_MMO}"
MODEL="${LBG_CLAUDE_OLLAMA_MODEL:-gemma4-claude}"
OLLAMA_BASE="http://${FRONT_HOST}:11434"

SSH_OPTS=(
  -o ConnectTimeout=8
  -o BatchMode=yes
  -o StrictHostKeyChecking=accept-new
  -o LogLevel=ERROR
)
[[ -n "${LBG_SSH_IDENTITY:-}" ]] && SSH_OPTS=( -i "${LBG_SSH_IDENTITY}" "${SSH_OPTS[@]}" )

fail=0
warn=0

log() { echo "[verify_claude] $*"; }
ok() { echo "  OK   $*"; }
ko() { echo "  KO   $*" >&2; fail=1; }
info() { echo "  INFO $*"; }
note() { echo "  NOTE $*"; warn=1; }

json_env_val() {
  local file="$1" key="$2"
  if command -v jq >/dev/null 2>&1; then
    jq -r --arg k "$key" '.env[$k] // empty' "$file" 2>/dev/null || true
    return
  fi
  python3 - "$file" "$key" <<'PY' 2>/dev/null || true
import json, sys
path, key = sys.argv[1], sys.argv[2]
with open(path, encoding="utf-8") as f:
    data = json.load(f)
env = data.get("env") or {}
print(env.get(key, ""))
PY
}

find_windows_repo() {
  if [[ -n "${LBG_WINDOWS_REPO:-}" && -d "${LBG_WINDOWS_REPO}" ]]; then
    echo "${LBG_WINDOWS_REPO}"
    return
  fi
  local candidates=(
    "/mnt/c/Users/${USER}/projects/LBG_IA_MMORPG"
    "/mnt/c/Users/${USER}/Documents/LBG_IA_MMORPG"
    "/mnt/j/projects/LBG_IA_MMORPG"
  )
  local c
  for c in "${candidates[@]}"; do
    if [[ -f "${c}/.claude/settings.json" ]]; then
      echo "$c"
      return
    fi
  done
}

check_ollama() {
  log "=== Ollama @${FRONT_HOST} ==="
  if curl -sf --max-time 5 "${OLLAMA_BASE}/api/version" >/dev/null 2>&1; then
    ok "Ollama joint (${OLLAMA_BASE})"
  else
    ko "Ollama injoignable (${OLLAMA_BASE})"
    return
  fi
  if curl -sf --max-time 8 "${OLLAMA_BASE}/api/tags" | grep -q "${MODEL}"; then
    ok "Modèle ${MODEL} présent"
  else
    ko "Modèle ${MODEL} absent sur Ollama"
  fi
}

check_settings_file() {
  local label="$1" file="$2"
  log "=== Settings ${label} ==="
  if [[ ! -f "$file" ]]; then
    ko "Fichier absent : ${file}"
    return
  fi
  ok "Fichier présent : ${file}"

  local base_url auth model
  base_url="$(json_env_val "$file" ANTHROPIC_BASE_URL)"
  auth="$(json_env_val "$file" ANTHROPIC_AUTH_TOKEN)"
  model="$(json_env_val "$file" ANTHROPIC_MODEL)"

  [[ "$base_url" == "${OLLAMA_BASE}" ]] && ok "ANTHROPIC_BASE_URL=${base_url}" \
    || ko "ANTHROPIC_BASE_URL=${base_url:-?} (attendu ${OLLAMA_BASE})"
  [[ "$auth" == "ollama" ]] && ok "ANTHROPIC_AUTH_TOKEN=ollama" \
    || ko "ANTHROPIC_AUTH_TOKEN=${auth:-?} (attendu ollama)"
  [[ "$model" == "${MODEL}" ]] && ok "ANTHROPIC_MODEL=${model}" \
    || ko "ANTHROPIC_MODEL=${model:-?} (attendu ${MODEL})"
}

check_launcher() {
  local label="$1" script="$2"
  log "=== Lanceur ${label} ==="
  if [[ ! -f "$script" ]]; then
    ko "Script absent : ${script}"
    return
  fi
  ok "Script présent"
  grep -qE "11434|LBG_LAN_HOST_FRONT|OLLAMA_BASE" "$script" \
    && ok "URL Ollama dans le script" \
    || ko "URL Ollama manquante ou incorrecte dans ${script}"
  grep -q "${MODEL}" "$script" \
    && ok "Modèle ${MODEL} dans le script" \
    || ko "Modèle ${MODEL} manquant dans ${script}"
}

check_local_claude() {
  log "=== Claude local (WSL/poste dev) ==="
  local launcher="${ROOT}/infra/scripts/claude_ollama_lan.sh"
  check_launcher "Linux/WSL" "$launcher"
  if [[ -x "${HOME}/.local/bin/claude" || -f "${HOME}/.local/bin/claude" ]]; then
    if bash "$launcher" --version >/dev/null 2>&1; then
      ok "claude_ollama_lan.sh --version ($(bash "$launcher" --version 2>/dev/null | head -1))"
    else
      note "Claude installé mais lanceur Ollama en échec (réseau ou binaire)"
    fi
  else
    info "Claude Code non installé localement (optionnel si travail uniquement sur 140)"
  fi
}

check_windows_repo() {
  local win_repo
  win_repo="$(find_windows_repo || true)"
  log "=== Poste Windows (repo) ==="
  if [[ -z "$win_repo" ]]; then
    info "Repo Windows non trouvé (définir LBG_WINDOWS_REPO si besoin)"
    return
  fi
  ok "Repo Windows : ${win_repo}"
  check_settings_file "Windows (.claude)" "${win_repo}/.claude/settings.json"
  check_launcher "Windows" "${win_repo}/scripts/claude-ollama-lan.ps1"
}

check_vm140() {
  log "=== VM 140 (${VM_USER}@${CORE_HOST}) ==="
  if ! ssh "${SSH_OPTS[@]}" "${VM_USER}@${CORE_HOST}" "true" 2>/dev/null; then
    ko "SSH ${VM_USER}@${CORE_HOST} indisponible (utiliser compte lbg + clé)"
    return
  fi
  ok "SSH ${VM_USER}@${CORE_HOST}"

  local remote_checks
  remote_checks="$(ssh "${SSH_OPTS[@]}" "${VM_USER}@${CORE_HOST}" bash -s <<EOF
set -euo pipefail
APP="${REMOTE_DIR}"
MODEL="${MODEL}"
OLLAMA="${OLLAMA_BASE}"
fail=0
check() { echo "  OK   \$1"; }
err() { echo "  KO   \$1"; fail=1; }

[[ -f "\${APP}/.claude/settings.json" ]] && check "settings projet" || err "settings projet absent"
[[ -f "\${APP}/infra/scripts/claude_ollama_lan.sh" ]] && check "claude_ollama_lan.sh" || err "lanceur absent"
[[ -f "\${APP}/CLAUDE.md" ]] && check "CLAUDE.md" || err "CLAUDE.md absent"
grep -q "claude-lbg" "\${HOME}/.bashrc" 2>/dev/null && check "alias claude-lbg" || err "alias claude-lbg absent"
grep -q "claude_ollama_lan.sh" "\${HOME}/.bashrc" 2>/dev/null && check "alias → Ollama" || err "alias sans Ollama"

if command -v jq >/dev/null 2>&1; then
  base=\$(jq -r '.env.ANTHROPIC_BASE_URL // empty' "\${APP}/.claude/settings.json" 2>/dev/null || true)
  model=\$(jq -r '.env.ANTHROPIC_MODEL // empty' "\${APP}/.claude/settings.json" 2>/dev/null || true)
else
  base=\$(python3 -c "import json; d=json.load(open('\${APP}/.claude/settings.json')); print(d.get('env',{}).get('ANTHROPIC_BASE_URL',''))" 2>/dev/null || true)
  model=\$(python3 -c "import json; d=json.load(open('\${APP}/.claude/settings.json')); print(d.get('env',{}).get('ANTHROPIC_MODEL',''))" 2>/dev/null || true)
fi
[[ "\$base" == "\${OLLAMA}" ]] && check "BASE_URL=\$base" || err "BASE_URL=\${base:-?}"
[[ "\$model" == "\${MODEL}" ]] && check "MODEL=\$model" || err "MODEL=\${model:-?}"

if bash "\${APP}/infra/scripts/claude_ollama_lan.sh" --version >/dev/null 2>&1; then
  ver=\$(bash "\${APP}/infra/scripts/claude_ollama_lan.sh" --version 2>/dev/null | head -1)
  check "lanceur --version (\$ver)"
else
  err "lanceur --version en échec"
fi

exit \$fail
EOF
)"
  echo "$remote_checks"
  if echo "$remote_checks" | grep -q "  KO "; then
    fail=1
  fi
}

compare_dev_vs_remote() {
  log "=== Comparaison WSL (LBG_IA_MMO) ↔ 140 ==="
  local local_file="${ROOT}/.claude/settings.json"
  local remote_file="${REMOTE_DIR}/.claude/settings.json"
  if [[ ! -f "$local_file" ]]; then
    note "Pas de ${local_file} en local (utiliser repo Windows ou déployer)"
    return
  fi
  local remote_json
  remote_json="$(ssh "${SSH_OPTS[@]}" "${VM_USER}@${CORE_HOST}" "cat '${remote_file}'" 2>/dev/null || true)"
  if [[ -z "$remote_json" ]]; then
    ko "Impossible de lire settings distant"
    return
  fi
  local keys=(ANTHROPIC_BASE_URL ANTHROPIC_AUTH_TOKEN ANTHROPIC_MODEL)
  local k lv rv
  for k in "${keys[@]}"; do
    lv="$(json_env_val "$local_file" "$k")"
    rv="$(echo "$remote_json" | python3 -c "import json,sys; d=json.load(sys.stdin); print((d.get('env') or {}).get(sys.argv[1],''))" "$k" 2>/dev/null || true)"
    if [[ "$lv" == "$rv" && -n "$lv" ]]; then
      ok "${k} identique (${lv})"
    else
      ko "${k} diverge : local=${lv:-?} remote=${rv:-?}"
    fi
  done
}

print_summary() {
  echo
  log "=== Résumé ==="
  if [[ "$fail" -eq 0 ]]; then
    echo "  Alignement Claude OK (Windows/WSL ↔ 140 ↔ Ollama ${FRONT_HOST})."
    [[ "$warn" -eq 1 ]] && echo "  Avertissements présents (voir NOTE/INFO ci-dessus)."
    echo
    echo "  Lancer Claude :"
    echo "    Windows : .\\scripts\\claude-ollama-lan.ps1"
    echo "    140     : ssh ${VM_USER}@${CORE_HOST} → claude-lbg"
    return 0
  fi
  echo "  Échecs détectés — corriger les lignes KO ci-dessus." >&2
  echo "  Rappel : sur 140, utiliser le compte ${VM_USER} (pas sdesharches)." >&2
  return 1
}

# --- main ---
log "Racine LBG_IA_MMO : ${ROOT}"
log "Repo parent       : ${REPO_ROOT}"
echo

check_ollama
echo
check_settings_file "WSL/LBG_IA_MMO" "${ROOT}/.claude/settings.json"
check_settings_file "repo parent" "${REPO_ROOT}/.claude/settings.json" 2>/dev/null || true
echo
check_local_claude
echo
check_windows_repo
echo
check_vm140
echo
compare_dev_vs_remote
echo
print_summary
