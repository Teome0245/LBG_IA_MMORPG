# Ops — Pont interne (auth + rate‑limit)

Ce document décrit les garde‑fous “service→service” pour le pont :

- `mmmorpg_server` (VM 245) → backend (VM 140) : `POST /v1/pilot/internal/route`
- backend (VM 140) → HTTP interne `mmmorpg_server` (VM 245) : lecture snapshot Lyra (déjà géré séparément)

## 1) Objectifs

- **Éviter les appels non souhaités** sur un endpoint interne LAN (token service).
- **Limiter les boucles / spams accidentels** (rate‑limit best‑effort).
- **Garder une rotation simple** (changer le token sans “déployer du code”).

## 2) Variables (source de vérité : `/etc/lbg-ia-mmo.env`)

### 2.1 Backend (VM 140)

- `LBG_PILOT_INTERNAL_TOKEN`
  - Si défini, les endpoints internes/ops suivants exigent le header :
    - `X-LBG-Service-Token: <token>`
  - Endpoints concernés :
    - `POST /v1/pilot/internal/route` (pont WS→IA, service→service)
    - `POST /v1/pilot/reputation` (écriture “réputation locale” via commit, sans LLM)
- `LBG_PILOT_INTERNAL_RL_RPS`
- `LBG_PILOT_INTERNAL_RL_BURST`
  - Rate‑limit best‑effort **par IP** (désactivé si \(rps \le 0\) ou \(burst \le 0\)).

### 2.2 Serveur WS (VM 245)

- `MMMORPG_IA_BACKEND_URL="http://192.168.0.140:8000"`
- `MMMORPG_IA_BACKEND_PATH="/v1/pilot/internal/route"`
- `MMMORPG_IA_BACKEND_TOKEN` (doit matcher `LBG_PILOT_INTERNAL_TOKEN`)

### 2.3 Serveur monde HTTP `mmo_server` (VM 245)

- `LBG_MMO_INTERNAL_TOKEN`
  - Si défini, les endpoints internes d’écriture du monde exigent le header :
    - `X-LBG-Service-Token: <token>`
  - Endpoint concerné :
    - `POST /internal/v1/npc/{npc_id}/reputation` (applique un delta, borné \([-100, 100]\))
  - But : garder le fallback `meta.source=mmo_world` cohérent si le snapshot WS est indisponible.

## 3) Valeurs recommandées (LAN)

- `LBG_PILOT_INTERNAL_RL_RPS=2`
- `LBG_PILOT_INTERNAL_RL_BURST=4`

Si tu fais du benchmark (`--repeat`), monte temporairement `burst` (ex. 10) ou désactive RL (mettre rps/burst à 0) le temps de la mesure.

## 4) Rotation du token (procédure)

1. Générer un token (ex. `python3 -c 'import secrets; print(secrets.token_urlsafe(32))'`).
2. Mettre à jour **en même temps** :
   - `LBG_PILOT_INTERNAL_TOKEN` (VM 140)
   - `MMMORPG_IA_BACKEND_TOKEN` (VM 245)
3. Pousser `/etc/lbg-ia-mmo.env` sur les VM via :
   - `infra/scripts/push_secrets_vm.sh`
4. Redémarrer les services (le script le fait si `LBG_RESTART_SERVICES=1`) :
   - `lbg-backend` (140)
   - `lbg-mmmorpg-ws` (245)
5. Valider (section suivante).

## 5) Validation rapide

### 5.1 Backend interne (140)

- Sans token : attendu **401** (si `LBG_PILOT_INTERNAL_TOKEN` est défini)
- Avec token : attendu **200**

Endpoints à valider :
- `POST /v1/pilot/internal/route`
- `POST /v1/pilot/reputation`

### 5.2 Pont WS→IA (245)

Utiliser le CLI :

```bash
.venv/bin/python mmmorpg_server/tools/ws_ia_cli.py --ws ws://192.168.0.245:7733 \
  --npc-id npc:innkeeper --npc-name "Mara l’aubergiste" \
  --text "Test" --final-only --timeout-s 60
```

Attendu :
- `ok: true`
- `trace_id` **non vide**

## 6) Ops cache dialogue (agent :8020)

### 6.1 Reset cache

Endpoint : `POST http://192.168.0.140:8020/admin/cache/reset`

- Si `LBG_DIALOGUE_ADMIN_TOKEN` est **défini** sur le service dialogue, il faut fournir :
  - `X-LBG-Service-Token: <token>`
- Sans token (ou token invalide) : attendu **401**
- Avec token valide : attendu **200**

### 6.2 Stats cache (healthz)

`GET http://192.168.0.140:8020/healthz` renvoie `cache` :
- compteurs globaux (`hits`, `misses`, `size`)
- et `by_speaker` (top) pour voir quels PNJ bénéficient le plus du cache.

