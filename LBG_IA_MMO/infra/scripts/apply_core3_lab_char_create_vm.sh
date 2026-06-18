#!/usr/bin/env bash
# Désactive la limite « 1 perso / heure » sur les instances Core3 VM (config-local.lua).
set -euo pipefail

VM_HOST="${LBG_NEW_MMO_VM_HOST:-192.168.0.245}"
VM_USER="${LBG_NEW_MMO_VM_USER:-lbg}"
COOLDOWN_MS="${CORE3_CHAR_CREATE_COOLDOWN_MS:-0}"

apply_one() {
  local conf="$1"
  local label="$2"
  ssh "${VM_USER}@${VM_HOST}" "bash -s" <<REMOTE
set -euo pipefail
CONF="${conf}"
MS="${COOLDOWN_MS}"
touch "\${CONF}"
if grep -q 'CharacterCreateCooldownMs' "\${CONF}"; then
  sed -i 's/Core3.PlayerCreationManager.CharacterCreateCooldownMs = [0-9]*/Core3.PlayerCreationManager.CharacterCreateCooldownMs = '\${MS}'/' "\${CONF}"
else
  cat >> "\${CONF}" <<LUA

-- lab : création perso sans délai 1h (apply_core3_lab_char_create_vm.sh)
Core3.PlayerCreationManager = {
	CharacterCreateCooldownMs = \${MS},
}
LUA
fi
echo "=== ${label} ==="
grep 'CharacterCreateCooldownMs' "\${CONF}" || true
REMOTE
}

echo "=== CharacterCreateCooldownMs=${COOLDOWN_MS} sur ${VM_HOST} ==="
apply_one "/opt/lbg-new-mmo-clean/MMOCoreORB/bin/conf/config-local.lua" "Prime (clean)"
apply_one "/opt/lbg-new-mmo/MMOCoreORB/bin/conf/config-local.lua" "PreCu (stock)"

echo ""
echo "Rebuild requis pour que le C++ lise la clé :"
echo "  bash infra/scripts/build_core3_antigravity_vm.sh"
echo "  bash infra/scripts/install_core3_dual_after_build.sh"
echo ""
echo "Déblocage SQL Bot_IA : mysql < infra/snippets/core3-clear-char-create-cooldown.sql"
