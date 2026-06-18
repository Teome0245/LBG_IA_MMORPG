# LBG Client Godot — Phase 0

Client minimal **Godot 4.2+** connecté au serveur **`mmmorpg_server`** (WebSocket JSON `mmmorpg-ws/1`).

Plan complet : [`../docs/plan_client_lbg_godot.md`](../docs/plan_client_lbg_godot.md).

## Prérequis

- [Godot 4.2+](https://godotengine.org/download)
- Serveur WS actif sur la VM MMO (port **7733** par défaut)

```bash
# Depuis LBG_IA_MMO (si service systemd déjà installé)
ssh lbg@192.168.0.245 'systemctl status lbg-mmmorpg-ws'

# Ou lancer en local pour test
cd LBG_IA_MMO
python -m mmmorpg_server
```

## Lancer le client

1. Ouvrir ce dossier dans Godot : **Importer** → `lbg_client_godot/project.godot`
2. **F5** (scène principale `Login.tscn`)
3. Choisir le serveur :
   - **Terre1 — mmmorpg (7733)** : bac à sable + **dialogue PNJ** (si `MMMORPG_IA_BACKEND_URL` actif sur la VM)
   - **Tatooine Prime — gateway (50000)** : PNJ IA depuis `npc_snapshots.json` (lancer le gateway avant)
4. Hôte `192.168.0.245`, nom joueur → **Connexion**
5. En monde : **ZQSD/WASD** — **Tab** = changer de PNJ cible — **Entrée** dans le chat = parler au PNJ

### Gateway Prime (port 50000)

```bash
bash infra/scripts/run_lbg_gateway_vm.sh
# ou en local :
LBG_GATEWAY_SNAPSHOTS=content/core3/ia_bridge/npc_snapshots.json \
PYTHONPATH=. python3 services/lbg_gateway/main.py
```

## Structure

| Chemin | Rôle |
|--------|------|
| `autoload/Network.gd` | WebSocket, `hello`, `move` |
| `autoload/GameState.gd` | Cache entités / `player_id` |
| `autoload/Config.gd` | Hôte / port |
| `scenes/Login.tscn` | Connexion |
| `scenes/World.tscn` | Monde 3D + entités |
| `scenes/EntityView.tscn` | Capsule + label par entité |

## Smoke sans Godot

```bash
bash infra/scripts/smoke_lbg_client_ws_phase0.sh
bash infra/scripts/smoke_lbg_client_ws_phase0.sh --host 127.0.0.1
```

## Suite (Phase 1+)

- `CharacterSelect.tscn` pour proto `lbg-ws/1` (gateway Core3)
- Dialogue PNJ via `hello` + `world_npc_id` + `text`
- Assets maps LBG (GLB)
