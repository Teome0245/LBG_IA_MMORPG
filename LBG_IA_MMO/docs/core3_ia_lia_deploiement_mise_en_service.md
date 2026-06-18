# Lia — déploiement mise en service (orchestrateur + connexion jeu)

**Date** : 2026-05-24  
**Statut** : déployé sur LAN (VM **140** orchestrateur, VM **245** Prime / sidecar / headless)

## Objectif

- **Lia** = incarnation IG de l’orchestrateur (`POST /v1/lia/hear`, `/v1/lia/tick`).
- **Connexion** = l’orchestrateur peut lancer / attendre la session headless `core3client` (`POST /v1/lia/connect`).

## Architecture déployée

| VM | IP | Rôle |
|----|-----|------|
| **140** | `192.168.0.140` | `lbg-orchestrator` :8010, `LBG_CORE3_IA_SIDECAR_URL=http://192.168.0.245:8791` |
| **245** | `192.168.0.245` | Prime, sidecar :8791 (`0.0.0.0`), `lbg-core3-ia-bot-client`, screenplay Lua |

## Étapes réalisées (2026-05-24)

### 1. Code synchronisé

Fichiers poussés via `infra/scripts/deploy_lia_orchestrator_incarnation.sh` :

| Composant | Fichiers |
|-----------|----------|
| Agents | `lia_orchestrator.py`, `lia_connection.py`, `lia_autonomy.py`, `core3_bridge.py` |
| Orchestrateur | `router/routes/lia_incarnation.py`, `router/v1.py`, `services/lia_autonomy.py` |
| Sidecar | `tools/core3_ia_sidecar/core3_ia_sidecar.py` (`/v1/lia/connect`) |
| Jeu | `content/core3/lua/ia_bridge_screenplay.lua`, `lia_orchestrator_persona.json` |
| Ops | `infra/scripts/run_core3_ia_bot_client_vm.sh` |

### 2. Variables `/etc/lbg-core3-ia.env`

Sur **140** et **245** (valeurs communes) :

```bash
LBG_CORE3_IA_SIDECAR_URL=http://192.168.0.245:8791   # 140 uniquement (URL LAN)
LBG_ORCHESTRATOR_URL=http://192.168.0.140:8010
LBG_CORE3_LIA_ACTOR_ID=orchestrator:lia
LBG_CORE3_LIA_AUTO_CONNECT=1
LBG_CORE3_LIA_CONNECT_WAIT_S=120
LBG_CORE3_LIA_CONNECT_MODE=systemd
LBG_CORE3_LIA_BOT_SYSTEMD_UNIT=lbg-core3-ia-bot-client.service
CORE3_IA_BOT_CHARACTER=Lia
```

Sur **140** en plus :

```bash
LBG_CORE3_LIA_AUTONOMY_ENABLED=1
LBG_CORE3_LIA_AUTONOMY_MODE=invoke
LBG_CORE3_LIA_AUTONOMY_INTERVAL_S=45
```

Sur **245** (boucle locale optionnelle, déjà présente) :

```bash
LBG_CORE3_LIA_AUTONOMY_ENABLED=1
LBG_CORE3_LIA_AUTONOMY_MODE=sidecar
LBG_CORE3_LIA_AUTONOMY_INTERVAL_S=30
```

### 3. Systemd corrigé

| Unité | Correction |
|-------|------------|
| `lbg-orchestrator.service` (140) | `EnvironmentFile=-/etc/lbg-core3-ia.env` (manquait sur la VM → sidecar URL non chargée) |
| `lbg-core3-ia-sidecar.service` (245) | `CORE3_IA_SIDECAR_HOST=0.0.0.0` (avant `127.0.0.1` → refus depuis 140) |

### 4. Services redémarrés

```bash
# 245
sudo systemctl restart lbg-core3-ia-sidecar
sudo systemctl enable --now lbg-core3-ia-bot-client

# 140
sudo systemctl restart lbg-orchestrator
```

### 5. Vérifications post-déploiement

| Test | Résultat attendu |
|------|------------------|
| `curl http://192.168.0.245:8791/healthz` depuis 140 | `ok: true` |
| `POST http://127.0.0.1:8010/v1/lia/connect` sur 140 | `already_online` ou `connected` |
| `POST http://127.0.0.1:8010/v1/lia/tick` sur 140 | `agent: core3_dispatch`, `ok: true` |
| `GET .../v1/player-snapshot?player=Lia` | `online: true` (si headless actif) |

Exemple :

```bash
ssh lbg@192.168.0.140 'curl -s -X POST http://127.0.0.1:8010/v1/lia/connect \
  -H "Content-Type: application/json" -d "{\"wait\":true,\"wait_s\":120}"'
```

## Script de redéploiement

```bash
cd LBG_IA_MMO
bash infra/scripts/deploy_lia_orchestrator_incarnation.sh
# avec test connexion :
bash infra/scripts/deploy_lia_orchestrator_incarnation.sh --connect-smoke
```

## Prérequis ops

1. **Prime** en marche (`lbg-core3-prime`).
2. Compte **Bot_IA** / perso **Lia**, `.env-core3client` sur 245 (`CORE3_CLIENT_LOGINHOST=192.168.0.245`).
3. **Une seule session** Lia : fermer le client SWG graphique avant le headless.
4. Secrets LLM dans `/etc/lbg-ia-mmo.env` (Groq / Ollama) pour `/v1/think`.

## Dépannage

| Symptôme | Cause probable | Action |
|----------|----------------|--------|
| `Connection refused` vers :8791 depuis 140 | Sidecar en `127.0.0.1` | `CORE3_IA_SIDECAR_HOST=0.0.0.0` + restart sidecar |
| `LBG_CORE3_IA_SIDECAR_URL non défini` | Orchestrateur sans `lbg-core3-ia.env` | Mettre à jour unité systemd + `daemon-reload` |
| `connect_timeout` | Login Prime / mot de passe / client bloqué | `journalctl -u lbg-core3-ia-bot-client -f` |
| `snapshot` online false mais log OK | Snapshot périmé | Attendre screenplay ; vérifier `online-players.log` |
| Actions enqueued mais invisibles | Tick Lua arrêté, queue non consommée | Vérifier `pending.jsonl` et `/tmp/core3-clean.log` ; `IA_BRIDGE_PLAYER_SNAPSHOT_FILE` doit être défini |
| `force_restart` | Client bloqué en boucle | `POST /v1/lia/connect` avec `"force_restart":true` |

## Documentation liée

- [Incarnation orchestrateur](core3_ia_lia_orchestrator_incarnation.md)
- [Phase D — headless](core3_ia_phase_d_headless_bot.md)
- [Phase E — autonomie](core3_ia_phase_e_lia_autonomy.md)
- [Phase F — multi-joueurs IA](core3_ia_phase_f_multi_players.md)
- [Phase G — population de joueurs IA](core3_ia_phase_g_ai_players_population.md)
