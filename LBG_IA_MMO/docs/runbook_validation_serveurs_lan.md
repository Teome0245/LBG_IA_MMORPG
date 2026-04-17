# Runbook — validation “serveurs OK” (LAN)

Objectif : en **2–5 minutes**, vérifier que la stack **serveurs** est saine et que le flux **WS hello → IA → commit → snapshot** fonctionne (avec placeholder remplacé via `trace_id`).

Topologie LAN par défaut :

- **core** : `192.168.0.140` (backend `:8000`, orchestrator `:8010`, agents `:8020/:8030/:8040`)
- **mmo** : `192.168.0.245` (mmo_server `:8050`, WS `:7733`, HTTP interne WS `:8773`)
- **front** : `192.168.0.110` (pilot_web statique)

---

## 0) Pré-requis

- Avoir un fichier `infra/secrets/lbg.env` cohérent (tokens + URLs LAN).
- Les services systemd tournent sur les VM (déployés via `infra/scripts/deploy_vm.sh`).

Optionnel (mais recommandé) :

- `LBG_DIALOGUE_WORLD_ACTIONS=1` sur le service **dialogue** (VM core) pour autoriser `ACTION_JSON` (aid borné).

---

## 1) Déploiement (si tu viens de changer du code)

Depuis `LBG_IA_MMO/` :

```bash
LBG_DEPLOY_ROLE=all bash infra/scripts/deploy_vm.sh
```

Puis pousser les secrets (et redémarrer services) :

```bash
bash infra/scripts/push_secrets_vm.sh
```

---

## 2) Santé rapide (HTTP)

```bash
curl -sS http://192.168.0.140:8000/healthz
curl -sS http://192.168.0.140:8000/v1/pilot/status | head -c 800 && echo
```

Attendu :

- `backend=ok`
- orchestrator `ok`
- agent dialogue `ok` (et `llm_configured=true` si LLM branché)
- mmo_server `ok`

---

## 3) Smokes LAN recommandés

### 3.0 Suite “CI style” (tout-en-un)

```bash
bash infra/scripts/smoke_lan_ci.sh
```

### 3.1 Commit “dialogue → aid_*” via API (service→service)

```bash
bash infra/scripts/smoke_dialogue_llm_action_commit_lan.sh
```

Attendu :

- `commit_result.accepted=true`
- `output.commit.flags` contient `aid_*`

### 3.2 Flux WS “joueur” : placeholder remplacé via `trace_id` + snapshot corrélé

```bash
bash infra/scripts/smoke_ws_hello_llm_aid_lan.sh
```

Attendu :

- Le script ignore le placeholder et attend la réponse finale.
- Snapshot “après” avec `lyra.meta.trace_id` identique au `trace_id` WS.

---

## 4) Validation manuelle via page web (avant Godot)

Ouvrir l’UI `pilot_web` (selon ton reverse-proxy / setup) :

- côté backend : `http://192.168.0.140:8000/pilot/`
- côté front (si servi) : `http://192.168.0.110/...` (selon Nginx)

Dans **WS (test client minimal)** :

- Clique **Connect**
- Clique **Send hello**
- Observe dans le log :
  - `npc_reply (placeholder, trace_id=...)`
  - puis `replace placeholder -> final (trace_id=...)`

Optionnel :

- Renseigne le champ **token service** (header `X-LBG-Service-Token`) pour que les snapshots `:8773` passent si protégés.

---

## 5) Dépannage express

- **Pas de réponse finale (placeholder seulement)** :
  - vérifier que `MMMORPG_IA_BACKEND_URL` pointe vers `http://192.168.0.140:8000`
  - augmenter `MMMORPG_IA_TIMEOUT_S` si LLM lent
  - regarder les logs : `journalctl -u lbg-mmmorpg-ws -n 100 --no-pager`

- **401 sur snapshot HTTP interne (`:8773`)** :
  - fournir `X-LBG-Service-Token` = `MMMORPG_INTERNAL_HTTP_TOKEN`
  - ou vérifier `infra/secrets/lbg.env` + `push_secrets_vm.sh`

- **Persistance “Permission denied” sur `/var/lib/lbg/...`** :
  - s’assurer que `/var/lib/lbg/mmmorpg` appartient à `lbg:lbg`
  - redeployer rôle `mmo` (le déploiement crée/chown ces répertoires).

