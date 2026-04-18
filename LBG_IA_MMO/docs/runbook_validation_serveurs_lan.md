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

## 2bis) Métriques (Prometheus texte, opt-in)

Par défaut, **`/metrics` est désactivé** (404) sur le backend et l’orchestrator, et sur l’HTTP interne `mmmorpg_server` (port **8773**).

Activation (systemd / `lbg.env`) :

- **backend** (`:8000`) et **orchestrator** (`:8010`) :
  - `LBG_METRICS_ENABLED=1`
  - optionnel (recommandé si exposé sur LAN) : `LBG_METRICS_TOKEN=<secret>` puis :

```bash
curl -sS -H "Authorization: Bearer <secret>" http://192.168.0.140:8000/metrics | head
curl -sS -H "Authorization: Bearer <secret>" http://192.168.0.140:8010/metrics | head
```

- **HTTP interne WS** (`192.168.0.245:8773`, service `mmmorpg_server`) :
  - `MMMORPG_INTERNAL_HTTP_METRICS=1`

```bash
curl -sS http://192.168.0.245:8773/metrics | head
```

Note sécurité : même “texte”, ces endpoints peuvent révéler de l’activité réseau / des compteurs internes — **ne les expose pas publiquement** sans token / firewall.

---

## 2ter) Checklist — activer les métriques après déploiement

Ordre recommandé (évite l’écueil « variables OK mais unités systemd anciennes », ou l’inverse) :

1. **Code + unités systemd** : depuis `LBG_IA_MMO/`, lancer **`LBG_DEPLOY_ROLE=all bash infra/scripts/deploy_vm.sh`** (ou au minimum le rôle qui recopie `infra/systemd/*.service` sur les VM concernées). Les unités **`lbg-backend`**, **`lbg-orchestrator`** et **`lbg-mmmorpg-ws`** embarquent des défauts sûrs (`LBG_METRICS_ENABLED=0`, `MMMORPG_INTERNAL_HTTP_METRICS=0` **avant** lecture de `/etc/lbg-ia-mmo.env`, de sorte que le fichier puisse activer les métriques).
2. **Variables runtime** : éditer **`infra/secrets/lbg.env`** (local, non versionné) en t’alignant sur **`infra/secrets/lbg.env.example`** ; pousser avec **`bash infra/scripts/push_secrets_vm.sh`** (recopie `/etc/lbg-ia-mmo.env` + redémarrage des services présents).
3. **Par rôle VM** :
   - **VM core (140)** : si besoin, `LBG_METRICS_ENABLED=1` et éventuellement `LBG_METRICS_TOKEN=…` pour **backend** et **orchestrator** (même fichier sur plusieurs hôtes : les services qui ne lisent pas la variable l’ignorent).
   - **VM MMO (245)** : si besoin, `MMMORPG_INTERNAL_HTTP_METRICS=1` pour l’HTTP interne **:8773** (`mmmorpg_server`).
4. **Vérification** : reprendre les `curl` de la section **2bis** ; un **404** sur `/metrics` signifie généralement « désactivé » ou mauvais hôte, un **401** indique un **token Bearer** attendu côté backend/orchestrator.

Référence UI : la page **`/pilot/`** propose des liens et des tests **GET /metrics** (Bearer optionnel, stocké dans le navigateur uniquement).

---

## 3) Smokes LAN recommandés

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
- **Métriques** : section **Monitoring** → liens `/metrics` + champ Bearer optionnel (voir **2ter**).

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

