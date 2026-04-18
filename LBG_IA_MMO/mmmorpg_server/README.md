# Serveur WebSocket `mmmorpg` (port monorepo)

Code **reproduit** depuis le dépôt source **`~/projects/mmmorpg/server/`** — **ne pas modifier** ce dépôt upstream ; les évolutions se font **ici**.

## Contenu

- Paquet Python : `src/mmmorpg_server/` (WebSocket, `world_tick`, entités Phase 1).
- Tests : `tests/` (dont intégration WS sur port libre).

## Protocole & suite

- Référence réseau : **`docs/mmmorpg_PROTOCOL.md`** (copie du PROTOCOL source au moment du portage).
- Backlog historique source : voir dépôt `mmmorpg` → `docs/SERVER_NEXT.md` (lecture seule).

## Installation (venv monorepo)

Depuis la racine **`LBG_IA_MMO/`** (après `install_local.sh`, qui peut inclure ce paquet) :

```bash
.venv/bin/pip install -e ./mmmorpg_server
```

## Lancer

```bash
cd LBG_IA_MMO
source .venv/bin/activate
PYTHONPATH=mmmorpg_server/src python -m mmmorpg_server
# ou après pip install -e :
python -m mmmorpg_server
```

Variables : `MMMORPG_HOST`, `MMMORPG_PORT` (défaut **7733**), `MMMORPG_TICK_RATE_HZ`, etc. (voir `mmmorpg_server/config.py`).

## HTTP interne (optionnel) — snapshot Lyra (lecture seule)

Pour la phase “pont lecture seule” (voir `docs/fusion_pont_jeu_ia.md`), le serveur WS peut exposer
une petite API HTTP interne (LAN / privé) qui renvoie un snapshot `context.lyra` minimal.

Activer :

- `MMMORPG_INTERNAL_HTTP_HOST` (défaut `127.0.0.1`)
- `MMMORPG_INTERNAL_HTTP_PORT` (défaut `0` = désactivé)
- `MMMORPG_INTERNAL_HTTP_TOKEN` (optionnel) : si défini, chaque requête doit inclure
  `X-LBG-Service-Token: <token>`

Endpoints :

- `GET /healthz`
- `GET /internal/v1/npc/{npc_id}/lyra-snapshot?trace_id=...`
- `POST /internal/v1/npc/{npc_id}/dialogue-commit` (phase 2, idempotent par `trace_id`)

Exemple :

```bash
curl -s "http://127.0.0.1:8773/internal/v1/npc/npc:merchant/lyra-snapshot?trace_id=t1"
```

Commit (ex.) :

```bash
curl -s "http://127.0.0.1:8773/internal/v1/npc/npc:merchant/dialogue-commit" \
  -H "content-type: application/json" \
  -d '{"trace_id":"t-commit-1","flags":{"quest_accepted":true}}'
```

## Tests

```bash
cd LBG_IA_MMO/mmmorpg_server
PYTHONPATH=src ../.venv/bin/python -m pytest tests/ -q
```

## CLI — smoke jalon gameplay WS → snapshot (sans LLM)

Depuis `LBG_IA_MMO/` (Python avec `websockets`, ex. `.venv-ci/bin/python` après `infra/ci/test_pytest.sh`) :

```bash
./.venv-ci/bin/python mmmorpg_server/tools/ws_world_commit_smoke.py \
  --ws ws://192.168.0.245:7733 \
  --internal http://192.168.0.245:8773 \
  --npc-id npc:merchant \
  --token "$LBG_MMMORPG_INTERNAL_HTTP_TOKEN" \
  --reputation-delta 7
```

Recette bash (racine `LBG_IA_MMO/`) : `bash infra/scripts/smoke_ws_move_commit_snapshot_lan.sh`.

## CLI E2E (LAN) — tester le pont WS → IA

Pré-requis :

- sur **245** : `lbg-mmmorpg-ws` actif + `MMMORPG_IA_BACKEND_URL` défini (voir `/etc/lbg-ia-mmo.env`)
- sur **140** : backend/orchestrator/agents actifs
- sur **110** : Ollama joignable (si dialogue LLM activé)

Commande (depuis la racine `LBG_IA_MMO/`) :

```bash
./.venv/bin/python mmmorpg_server/tools/ws_ia_cli.py \
  --ws ws://192.168.0.245:7733 \
  --npc-id npc:innkeeper \
  --npc-name "Mara l’aubergiste" \
  --text "Une chambre pour la nuit, s'il vous plaît."
```

Sortie attendue : `trace_id` + `npc_reply` (et une latence `elapsed_ms`).

### Benchmark (p50/p95)

```bash
./.venv/bin/python mmmorpg_server/tools/ws_ia_cli.py \
  --ws ws://192.168.0.245:7733 \
  --npc-id npc:innkeeper \
  --npc-name "Mara l’aubergiste" \
  --text "Une chambre pour la nuit, s'il vous plaît." \
  --repeat 10 \
  --sleep-ms 250 \
  --json
```

### Attendre la réponse “finale” (pas le placeholder)

Si `MMMORPG_IA_PLACEHOLDER_ENABLED=1`, le serveur peut renvoyer un `npc_reply` placeholder très vite,
puis une réponse finale avec `trace_id` non vide plus tard. Pour n’afficher que la finale :

```bash
./.venv/bin/python mmmorpg_server/tools/ws_ia_cli.py \
  --ws ws://192.168.0.245:7733 \
  --npc-id npc:innkeeper \
  --npc-name "Mara l’aubergiste" \
  --text "Une chambre pour la nuit, s'il vous plaît." \
  --timeout-s 120 \
  --final-only
```

### Suite (tours de dialogue) — réutiliser `move`

Après `hello`, tu peux enchaîner avec un `move` contenant `world_npc_id` + `text` (+ `npc_name` optionnel),
sans introduire de nouveau type WS (voir `docs/mmmorpg_PROTOCOL.md`).

## systemd (VM MMO, ex. 0.245)

Après **`LBG_DEPLOY_ROLE=mmo`** (`deploy_vm.sh`), unité **`lbg-mmmorpg-ws.service`** :

```bash
sudo systemctl status lbg-mmmorpg-ws
sudo journalctl -u lbg-mmmorpg-ws -f
```

Variables dans **`/etc/lbg-ia-mmo.env`** : `MMMORPG_HOST` (ex. `0.0.0.0` pour le LAN), `MMMORPG_PORT` (défaut **7733**), etc.

## Voir aussi

- `docs/plan_fusion_lbg_ia.md` — phase C (portage).
- `docs/adr/0002-mmo-autorite-pont.md` — autorité jeu vs `mmo_server`.
- `infra/systemd/lbg-mmmorpg-ws.service` — unité installée par le rôle **mmo**.
