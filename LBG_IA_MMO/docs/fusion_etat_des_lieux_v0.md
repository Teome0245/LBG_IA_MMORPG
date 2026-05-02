# État des lieux fusion v0

Document de **phase A** du plan de fusion (`plan_fusion_lbg_ia.md`) : photographie des surfaces **HTTP / réseau** et des **variables** utiles au pont entre les trois lignées — **sans modifier** les dépôts sources **`LBG_IA`** et **`mmmorpg`**.

**Date** : 2026-04-12  
**Références** : ADR `adr/0001-tronc-monorepo.md`, topologie LAN `fusion_env_lan.md`, lexique `lexique.md`.

---

## 1. Monorepo `LBG_IA_MMO/` (tronc cible)

### 1.1 Services FastAPI — chemins OpenAPI

Regénérer la liste des chemins (depuis la racine `LBG_IA_MMO/`, venv : `.venv/bin/python`) :

```bash
( cd backend && PYTHONPATH=. python -c "from main import app; print(sorted(app.openapi()['paths']))" )
( cd orchestrator && PYTHONPATH=. python -c "from main import app; print(sorted(app.openapi()['paths']))" )
( cd mmo_server && PYTHONPATH=. python -c "from http_app import app; print(sorted(app.openapi()['paths']))" )
```

| Service | Port typique (dev) | Préfixe OpenAPI |
|---------|-------------------|-----------------|
| **Backend** | 8000 | Voir tableau |
| **Orchestrateur** | 8010 | Voir tableau |
| **`mmo_server`** (HTTP Lyra) | 8050 | Voir tableau |

**Backend** (`backend/main.py`, préfixe API `/v1`) :

| Méthode | Chemin |
|---------|--------|
| GET | `/healthz` |
| POST | `/v1/intents/route` |
| GET | `/v1/pilot/status` |
| GET | `/v1/pilot/capabilities` |
| POST | `/v1/pilot/route` |
| GET | `/v1/pilot/agent-dialogue/healthz` |
| GET | `/v1/pilot/agent-dialogue/npc-registry` |
| GET | `/v1/pilot/agent-dialogue/world-content` |
| GET | `/v1/pilot/agent-quests/healthz` |
| GET | `/v1/pilot/agent-combat/healthz` |
| GET | `/v1/pilot/mmo-server/healthz` |

Fichiers statiques : **`GET /pilot/`** (et assets sous `/pilot/…`) via `StaticFiles` sur le répertoire `pilot_web/`.

**Orchestrateur** (`orchestrator/main.py`) :

| Méthode | Chemin |
|---------|--------|
| GET | `/healthz` |
| GET | `/v1/capabilities` |
| POST | `/v1/route` |

**`mmo_server`** (`mmo_server/http_app.py`) :

| Méthode | Chemin |
|---------|--------|
| GET | `/healthz` |
| GET | `/v1/world/lyra` |

### 1.2 Agents HTTP (`lbg_agents` — apps séparées)

Chaque agent expose typiquement **`GET /healthz`** et **`POST /invoke`** (pas montés sur le backend principal).

| Module | Port systemd / doc |
|--------|---------------------|
| `dialogue_http_app` | 8020 |
| `quests_http_app` | 8030 |
| `combat_http_app` | 8040 |

Détail : `agents/README.md`.

---

## 2. Dépôt source `LBG_IA/` (référence — pas de modification)

**Chemin typique** : `~/projects/LBG_IA/`.

L’API FastAPI principale du routeur / Lyra / monde vit sous  
**`orchestrateur/backend/`** (`src/app/factory.py`).

**Source de vérité déjà rédigée dans le dépôt source** :

- **`orchestrateur/backend/docs/HTTP_ROUTES.md`** — inventaire des routers (`/health`, `/ask`, `/execute`, `/lyra/...`, `/agents/...`, `/world/...`, `/godot/...`, etc.).

Pour la fusion, ce fichier sert de **liste de contrôle** lors du portage vers le monorepo (contrats, duplication à éviter, mapping vers `/v1/route` / capabilities MMO).

**Documentation projet** : `LBG_IA/docs/REFERENCE_PROJET_LBG_IA.md` (vue d’ensemble produit).

---

## 3. Dépôt source `mmmorpg/` (référence — pas de modification)

**Chemin typique** : `~/projects/mmmorpg/`.

### 3.1 Transport

- **WebSocket** (pas d’OpenAPI HTTP unique pour le jeu temps réel).  
- **`docs/PROTOCOL.md`** : messages `hello`, `move`, `welcome`, `world_tick`, `entity_snapshot`, `error`.

### 3.2 Variables d’environnement (extrait)

| Variable | Rôle (résumé) |
|----------|----------------|
| `MMMORPG_HOST` | Bind (ex. `0.0.0.0`) |
| `MMMORPG_PORT` | Port WS (ex. **7733**) |
| `MMMORPG_TICK_RATE_HZ` | Boucle monde (ex. 20) |
| `MMMORPG_MAX_WS_INBOUND_BYTES` | Taille max frame entrante |
| `MMMORPG_MOVE_MIN_INTERVAL_S` | Anti-spam `move` |

Source : `README.md` et `docs/PROTOCOL.md` du dépôt **mmmorpg**.

### 3.3 Points d’extension (pour futur pont IA)

- PNJ / entités dans les snapshots (`world_tick`, `entity_snapshot`).
- **`docs/SERVER_NEXT.md`** : backlog serveur ; à consulter lors du **portage dans le monorepo** (pas de modification du dépôt source).

---

## 4. Variables d’environnement — pont monorepo ↔ LAN

La table **opérationnelle** (IPs **140 / 245 / 110**, `LBG_*`, déploiement) est maintenue dans **`fusion_env_lan.md`**.

Comparatif **conceptuel** pour la fusion (à affiner lors du portage de code) :

| Rôle | Variables côté monorepo (extraits) | Commentaire |
|------|-----------------------------------|---------------|
| Chaîne pilot → IA | `LBG_ORCHESTRATOR_URL`, `LBG_BACKEND_PUBLIC_URL` | Aligner avec l’hôte qui expose backend + orchestrateur |
| Slice Lyra / monde PNJ | `LBG_MMO_SERVER_URL` | URL du **`mmo_server`** (HTTP) sur le LAN |
| LLM dialogue | `LBG_AGENT_DIALOGUE_URL`, `LBG_DIALOGUE_LLM_*` | Agent dialogue + modèle Ollama |
| Jeu (après intégration) | `MMMORPG_*` | À centraliser dans le schéma d’env du monorepo quand le serveur WS sera porté |

Une **table trois colonnes** (chaque variable × **LBG_IA** × **LBG_IA_MMO** × **mmmorpg**) pourra compléter ce document en **phase B** si besoin d’audit fin.

---

## 5. Synthèse et suite

| Thème | État (v0) |
|-------|-----------|
| Routes HTTP monorepo | Inventoriées (OpenAPI / agents) |
| Routes HTTP **LBG_IA** | Référencées via **`HTTP_ROUTES.md`** du dépôt source |
| **mmmorpg** | WS + PROTOCOL + variables `MMMORPG_*` |
| ADR tronc | **`adr/0001-tronc-monorepo.md`** accepté |
| Sous-ADR autorité monde / pont | **`adr/0002-mmo-autorite-pont.md`** accepté |
| Seed PNJ (`mmo_server`) | **`world/seed_data/world_initial.json`**, **`LBG_MMO_SEED_PATH`** |

**Prochaine étape documentaire recommandée** : **phase C** (`plan_fusion_lbg_ia.md`) — déploiement **`mmmorpg_server`** (7733) sur LAN, E2E réseau ; **code** — **`mmmorpg_server/`** présent dans le monorepo ; enrichissement seed / persistance.
