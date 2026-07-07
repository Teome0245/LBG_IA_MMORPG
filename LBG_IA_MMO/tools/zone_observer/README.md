# Zone observer (M1)

CLI lecture seule des snapshots `ia_bridge/` — même source que le gateway et les bots IA.

## Usage

```bash
cd LBG_IA_MMO

# Un affichage
python3 tools/zone_observer/zone_feed.py --once

# Watch 1 Hz (terminal)
python3 tools/zone_observer/zone_feed.py --watch --interval 1

# Export JSON pour prime-client (Godot)
python3 tools/zone_observer/zone_feed.py --watch --json-out /tmp/zone_feed.json --quiet

# Snapshots sur la VM Prime (après SSH mount ou copie)
IA_BRIDGE_DIR=/opt/lbg-new-mmo-clean/MMOCoreORB/bin/ia_bridge \
  python3 tools/zone_observer/zone_feed.py --watch

# M3 — mirroring retail → Godot (UDP 127.0.0.1:12345)
bash tools/zone_observer/run_m3_mirror.sh
# ou :
python3 tools/zone_observer/zone_feed.py --mirror --godot-port 12345
```

## Colonnes

| Champ | Source |
|-------|--------|
| `player` | `player_snapshots.json` (+ résolution intérieur via `locations/`) |
| `npc` | `npc_snapshots.json` |

## Tests

```bash
python3 -m unittest tools.zone_observer.test_zone_feed -v
```

## Client Godot (M2/M3)

Voir `new_mmo/prime-client` — `SnapshotBridge` lit le JSON ou les snapshots ; `--mirror` pousse en UDP vers `NetworkBridge` (prioritaire sur le poll fichier).
