#!/usr/bin/env bash
# Prépare deux instances Core3 sur la VM MMO (stock SWGEmu + build Antigravity « clean »).
# À lancer depuis LBG_IA_MMO sur le poste de dev (SSH vers la VM).
set -euo pipefail

VM_HOST="${LBG_NEW_MMO_VM_HOST:-192.168.0.245}"
VM_USER="${LBG_NEW_MMO_VM_USER:-lbg}"

STOCK_ROOT="/opt/lbg-new-mmo/MMOCoreORB"
CLEAN_ROOT="/opt/lbg-new-mmo-clean/MMOCoreORB"
TRE_PATH="/opt/lbg-new-mmo/tre"

SSH_OPTS=(-o ControlMaster=auto -o ControlPersist=5m -o "ControlPath=/tmp/lbg_core3_dual_%r@%h:%p")

echo "=== Setup dual Core3 sur ${VM_USER}@${VM_HOST} ==="

ssh "${SSH_OPTS[@]}" "${VM_USER}@${VM_HOST}" "bash -s" <<EOF
set -euo pipefail

STOCK_BIN="${STOCK_ROOT}/bin"
CLEAN_BIN="${CLEAN_ROOT}/bin"
STOCK_CONF="\${STOCK_BIN}/conf"
CLEAN_CONF="\${CLEAN_BIN}/conf"

# 1) Sauver le binaire SWGEmu encore en RAM (si un core3 tourne)
if pgrep -x core3 >/dev/null; then
  PID=\$(pgrep -x core3 | head -1)
  if [[ -r "/proc/\${PID}/exe" ]]; then
    cp "/proc/\${PID}/exe" /tmp/core3-swgemu-stock 2>/dev/null || true
    chmod +x /tmp/core3-swgemu-stock 2>/dev/null || true
    echo "Binaire stock capturé depuis PID \${PID}"
  fi
fi

# 2) Arborescence « clean » (copie sans Berkeley DB locale)
sudo mkdir -p /opt/lbg-new-mmo-clean
sudo rsync -a --delete \
  --exclude 'bin/databases/' \
  --exclude 'bin/log/' \
  --exclude 'bin/boot.log' \
  "${STOCK_ROOT}/" "${CLEAN_ROOT}/"
sudo chown -R ${VM_USER}:${VM_USER} /opt/lbg-new-mmo-clean

mkdir -p "\${CLEAN_BIN}/databases" "\${CLEAN_BIN}/log"
touch "\${CLEAN_BIN}/log/core3.log"

# 3) Binaires distincts (évite pkill ambigu entre /opt/lbg-new-mmo et …-clean)
if [[ -f /tmp/core3-swgemu-stock ]]; then
  cp /tmp/core3-swgemu-stock "\${STOCK_BIN}/core3-swgemu"
  chmod +x "\${STOCK_BIN}/core3-swgemu"
  echo "Stock core3-swgemu : \$(stat -c '%s bytes' "\${STOCK_BIN}/core3-swgemu")"
fi

if [[ -x "\${STOCK_BIN}/core3" ]] && [[ \$(stat -c%s "\${STOCK_BIN}/core3") -gt 60000000 ]]; then
  cp "\${STOCK_BIN}/core3" "\${CLEAN_BIN}/core3-clean"
elif [[ -f "\${STOCK_BIN}/core3_new" ]]; then
  cp "\${STOCK_BIN}/core3_new" "\${CLEAN_BIN}/core3-clean"
elif [[ -x "\${CLEAN_BIN}/core3" ]]; then
  cp "\${CLEAN_BIN}/core3" "\${CLEAN_BIN}/core3-clean"
fi
chmod +x "\${CLEAN_BIN}/core3-clean" 2>/dev/null || true
echo "Clean core3-clean : \$(stat -c '%s bytes' "\${CLEAN_BIN}/core3-clean" 2>/dev/null || echo missing)"

# 4) config-local clean (ports + galaxy 3) — préserve les secrets stock si présents
if [[ -f "\${STOCK_CONF}/config-local.lua" ]]; then
  DBPASS=\$(grep -E '^Core3\\.DBPass' "\${STOCK_CONF}/config-local.lua" | sed -n 's/.*= *"\\(.*\\)".*/\\1/p' | head -1)
fi
DBPASS="\${DBPASS:-123456}"

cat > "\${CLEAN_CONF}/config-local.lua" <<LUA
-- Instance Core3 clean (Antigravity) — généré par setup_core3_dual_vm.sh
Core3.TrePath = "${TRE_PATH}"
Core3.DBHost = "127.0.0.1"
Core3.DBPort = 3306
Core3.DBName = "swgemu"
Core3.DBUser = "swgemu"
Core3.DBPass = "\${DBPASS}"
Core3.MantisHost = "127.0.0.1"
Core3.MantisPort = 3306
Core3.MantisName = "swgemu"
Core3.MantisUser = "swgemu"
Core3.MantisPass = "\${DBPASS}"
Core3.LoginPort = 44553
Core3.PingPort = 44562
Core3.ORBPort = 44519
Core3.StatusPort = 44555
Core3.WebPorts = 44560
Core3.ZoneGalaxyID = 3
LUA

# 5) Galaxie SQL (galaxy_id = 3)
SQL_GALAXY="INSERT INTO galaxy (galaxy_id, name, address, port, pingport)
VALUES (3, 'LBG MMO Serveur Prime', '192.168.0.245', 44563, 44562)
ON DUPLICATE KEY UPDATE name=VALUES(name), address=VALUES(address), port=VALUES(port), pingport=VALUES(pingport);"
if mysql swgemu -e "\${SQL_GALAXY}" 2>/dev/null; then
  :
else
  sudo mysql swgemu -e "\${SQL_GALAXY}"
fi

echo "Galaxies :"
mysql -N swgemu -e 'SELECT galaxy_id,name,port,pingport FROM galaxy ORDER BY galaxy_id' 2>/dev/null \\
  || sudo mysql -N swgemu -e 'SELECT galaxy_id,name,port,pingport FROM galaxy ORDER BY galaxy_id'

echo "=== Setup terminé ==="
echo "  Stock : ${STOCK_ROOT}/bin/core3-swgemu  (ports 44453/44462/44463, galaxy 2)"
echo "  Clean : ${CLEAN_ROOT}/bin/core3-clean   (ports 44553/44562/44563, galaxy 3)"
EOF
