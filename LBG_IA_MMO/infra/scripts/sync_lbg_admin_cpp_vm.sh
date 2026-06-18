#!/usr/bin/env bash
# Sync sources C++ LBG admin (phase 1–2) vers Antigravity sur la VM — sans rsync complet.
set -euo pipefail

LBG="${LBG_MMO_ROOT:-$HOME/projects/new_mmo/lbg-mmo}"
VM="${LBG_NEW_MMO_VM_USER:-lbg}@${LBG_NEW_MMO_VM_HOST:-192.168.0.245}"
AG="/opt/lbg-antigravity/lbg-mmo"

rsync -az \
  "$LBG/server-core3/server/login/account/AdminLevelCompat.h" \
  "$LBG/server-core3/server/login/account/AccountManager.cpp" \
  "$LBG/server-core3/server/login/account/AccountImplementation.cpp" \
  "$VM:$AG/server-core3/server/login/account/"

rsync -az \
  "$LBG/server-core3/server/zone/managers/player/LbgAdminLevels.h" \
  "$VM:$AG/server-core3/server/zone/managers/player/"

rsync -az \
  "$LBG/server-core3/server/zone/managers/player/creation/PlayerCreationManager.cpp" \
  "$LBG/server-core3/server/zone/managers/player/creation/PlayerCreationManager.h" \
  "$VM:$AG/server-core3/server/zone/managers/player/creation/"

rsync -az \
  "$LBG/server-core3/server/zone/objects/player/PlayerObject.idl" \
  "$VM:$AG/server-core3/server/zone/objects/player/"

rsync -az \
  "$LBG/server-core3/server/zone/objects/creature/commands/WeatherCommand.h" \
  "$LBG/server-core3/server/zone/objects/creature/commands/ServerLootCommand.h" \
  "$LBG/server-core3/server/zone/objects/creature/commands/ServerStatisticsCommand.h" \
  "$LBG/server-core3/server/zone/objects/creature/commands/SpawnPointInAreaCommand.h" \
  "$LBG/server-core3/server/zone/objects/creature/commands/SetFirstNameCommand.h" \
  "$LBG/server-core3/server/zone/objects/creature/commands/SetLastNameCommand.h" \
  "$LBG/server-core3/server/zone/objects/creature/commands/PlayerManagerCommand.h" \
  "$LBG/server-core3/server/zone/objects/creature/commands/PlayerInfoCommand.h" \
  "$LBG/server-core3/server/zone/objects/creature/commands/PathFindCommand.h" \
  "$LBG/server-core3/server/zone/objects/creature/commands/MarketCommand.h" \
  "$VM:$AG/server-core3/server/zone/objects/creature/commands/"

echo "Sources admin LBG synchronisées vers $AG"
