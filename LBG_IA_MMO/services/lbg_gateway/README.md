# lbg_gateway — WebSocket `lbg-ws/1` (Core3 Prime v0)

Passerelle **lecture** vers les PNJ IA Core3 via `ia_bridge/npc_snapshots.json`.

## Lancer (LAN)

```bash
cd LBG_IA_MMO
export LBG_GATEWAY_SNAPSHOTS=/opt/lbg-new-mmo-clean/MMOCoreORB/bin/ia_bridge/npc_snapshots.json
export LBG_GATEWAY_CATALOG=content/core3/core3_npc_catalog.json
python3 -m services.lbg_gateway.main
# ou depuis la racine LBG_IA_MMO :
PYTHONPATH=. python3 services/lbg_gateway/main.py
```

Port par défaut : **50000** (`LBG_GATEWAY_PORT`).

## Client Godot

Login → **Tatooine Prime — gateway (50000)**.

## Dialogue IA (`interact`)

Si `LBG_GATEWAY_IA_BACKEND_URL` (ou `MMMORPG_IA_BACKEND_URL` sur la VM) pointe vers l’orchestrateur :

- `POST {url}/v1/pilot/internal/route` (même contrat que `mmmorpg_server`)
- `context.world_npc_id` = `pilot_id` catalogue (`npc:core3_barman_jax`, …)
- Réponse `type: chat` avec `trace_id` ; placeholder optionnel pendant l’appel

Déploiement VM :

```bash
bash infra/scripts/run_lbg_gateway_vm.sh
```

## Joueurs zone (lbgemu / bots) — lecture seule

Lit `ia_bridge/player_snapshots.json` sur la VM (écrit par le screenplay Lua ~2 s).

- Joueurs suivis : `LBG_GATEWAY_TRACK_PLAYERS` (défaut `Teome,Lia,Nix`)
- Entités `kind: player`, `source: core3`, id `player:Teome`, etc.
- Le client Godot affiche des capsules **turquoise** `[lbgemu]` ; votre avatar reste **bleu** `Vous (Godot)`.

Prérequis VM :

1. `ia_bridge_screenplay.lua` à jour (Teome inclus dans les snapshots multi-joueurs)
2. `deploy_core3_ia_bridge_vm.sh` ou redémarrage `core3-clean` après sync Lua
3. `player_snapshots.json` sous `MMOCoreORB/bin/ia_bridge/`

## Limites v0

- Login / persos : **stub** (accepte tout compte dev).
- Godot Prime : **mode observateur** (caméra sur Teome/Lia/Nix, pas de déplacement local).
- `move` Godot : met à jour l’avatar proxy gateway ; injection Core3 **optionnelle** (voir ci-dessous).
- Rosters `exactly_one` (ex. barmans cantina) : **un seul** PNJ du roster dans `world_state`.
- `world_state` : poll snapshots PNJ + joueurs zone + catalogue toutes les 2 s.

## Service systemd (VM)

```bash
bash infra/scripts/install_lbg_gateway_systemd_vm.sh
```

Fichier : `infra/systemd/lbg-gateway.service` + `gateway.env` sur la VM.

## Phase 3 — injection `pending.jsonl` (opt-in)

Variables (`gateway.env`) :

| Variable | Défaut | Rôle |
|----------|--------|------|
| `LBG_GATEWAY_PENDING_FILE` | — | Chemin `ia_bridge/pending.jsonl` |
| `LBG_GATEWAY_INJECT_MOVE` | `0` | `1` = append `move_to\|Teome\|…` à chaque `move` Godot |
| `LBG_GATEWAY_INJECT_PLAYER` | `Teome` | Prénom joueur cible |

Expérimental : coords proxy Godot (monde), pas encore converties cellule cantina.

## Suite v1

- Auth SQL `swgemu`
- `move` cantina en coords locales + hook zone C++
- Push deltas depuis hook C++
