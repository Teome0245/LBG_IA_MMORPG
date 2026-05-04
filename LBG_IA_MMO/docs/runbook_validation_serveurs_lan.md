# Runbook — validation “serveurs OK” (LAN)

Objectif : en **2–5 minutes**, vérifier que la stack **serveurs** est saine et que le flux **WS hello → IA → commit → snapshot** fonctionne (avec placeholder remplacé via `trace_id`).

Topologie LAN par défaut :

- **core** : `192.168.0.140` (backend `:8000`, orchestrator `:8010`, agents `:8020/:8030/:8040`)
- **mmo** : `192.168.0.245` (mmo_server `:8050`, WS `:7733`, HTTP interne WS `:8773`)
- **front** : `192.168.0.110` (Interface Unifiée Nginx `:8080`)

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

### 1bis) Déployer uniquement le client MMO `/mmo/` (anti‑régression)

Pour éviter les grosses régressions “front” :

- `infra/scripts/deploy_web_client.sh` fait un **déploiement atomique** (stage → switch) et refuse le déploiement si `index.html` référence des assets manquants.
- Il garde automatiquement un **backup** des derniers déploiements dans `mmo_releases/` sur la VM front (110).
- **Sans accès SSH** (poste de dev uniquement) : `LBG_MMO_WEB_DEPLOY_LOCAL_ONLY=1 bash infra/scripts/deploy_web_client.sh` exécute le build `--base=/mmo/`, les vérifications, et copie le `dist/` vers `LBG_IA_MMO/pilot_web/mmo/` (pas de rsync vers la VM).

Commande :

```bash
bash infra/scripts/deploy_web_client.sh
```

Rollback (si un rebuild a régressé le rendu ou la connexion) :

```bash
bash infra/scripts/rollback_web_client.sh
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

### 3.0 Cœur backend / orchestrateur + Pilot (sans HTTP interne `:8773` sur la VM MMO)

Quand tu veux valider **uniquement la VM core** (backend `:8000`, orchestrateur `:8010`, `GET /v1/pilot/status`) **sans** dépendre du serveur jeu / HTTP interne **mmmorpg** (`192.168.0.245:8773`) :

```bash
cd LBG_IA_MMO
bash infra/scripts/smoke_lan_core_desktop.sh
```

Option — enchaîner aussi un **`POST /v1/pilot/route`** avec `open_url` en **`desktop_dry_run`** (chaîne pilot → orchestrateur → `agent.desktop`, si configurée) :

```bash
bash infra/scripts/smoke_lan_core_desktop.sh --desktop-route
# ou : LBG_SMOKE_DESKTOP_ROUTE=1 bash infra/scripts/smoke_lan_core_desktop.sh
```

Depuis la racine du workspace parent (dossier contenant `LBG_IA_MMO/`), le même fichier existe comme **wrapper** : `bash infra/scripts/smoke_lan_core_desktop.sh`.

Dans **`infra/scripts/smoke_lan_quick.sh`**, tu peux ajouter **`LBG_SMOKE_WITH_CORE_DESKTOP=1`** : une étape **supplémentaire** (healthz core + orchestrateur + `GET /v1/pilot/status`, sans **`:8773`**) après les autres smokes optionnels. **Attention** : le *quick* enchaîne par défaut **`smoke_lan_minimal.sh`**, qui interroge aussi la VM MMO — pour **uniquement** le cœur sans accès mmmorpg, lance **`smoke_lan_core_desktop.sh`** seul (sans le *quick*).

### 3.0.1 Proxies Pilot → agents (GET healthz, sans route)

Vérifie que le **backend** répond en proxy pour les healthz **`agent-dialogue`**, **`agent-desktop`**, **`agent-pm`** :

```bash
cd LBG_IA_MMO
bash infra/scripts/smoke_lan_pilot_agent_proxies.sh
```

Codes **502** / **503** sur une ligne indiquent souvent l’agent **non branché** — le script reste en **exit 0** sauf si **`LBG_SMOKE_AGENT_PROXIES_STRICT=1`** (alors toute réponse hors **2xx** fait échouer le smoke).

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
- côté front (Interface Unifiée) : `http://192.168.0.110:8080/` (Lyra) ou `http://192.168.0.110:8080/mmo/` (MMO)

Dans **WS (test client minimal)** :

- Clique **Connect**
- Clique **Send hello**
- Observe dans le log :
  - `npc_reply (placeholder, trace_id=...)`
  - puis `replace placeholder -> final (trace_id=...)`

Optionnel :

- Renseigne le champ **token service** (header `X-LBG-Service-Token`) pour que les snapshots `:8773` passent si protégés.
- **Métriques** : section **Monitoring** → liens `/metrics` + champ Bearer optionnel (voir **2ter**).
- **Desktop (hybride)** : `#/desktop` — presets d’actions, dry-run pilot, **Proposer via IA** si l’agent dialogue expose le plan desktop ; détail `docs/desktop_hybride.md`, recette HTTP **3.0**.

---

## 5) Dépannage express

- **Pas de réponse finale (placeholder seulement)** :
  - vérifier que `MMMORPG_IA_BACKEND_URL` pointe vers `http://192.168.0.140:8000`
  - augmenter `MMMORPG_IA_TIMEOUT_S` si LLM lent
  - regarder les logs : `journalctl -u lbg-mmmorpg-ws -n 100 --no-pager`

- **HUD figé côté client `/mmo/` (HP/MP/Énergie ne bougent pas)** :
  - vérifier que le serveur WS inclut `stats` dans les snapshots d’entités (`Entity.to_snapshot()`), sinon le client n’a rien à rafraîchir
  - vérifier côté serveur que `GameState.apply_player_move()` initialise `ent.stats` (hp/mp/stamina/level/exp…)

- **401 sur snapshot HTTP interne (`:8773`)** :
  - fournir `X-LBG-Service-Token` = `MMMORPG_INTERNAL_HTTP_TOKEN`
  - ou vérifier `infra/secrets/lbg.env` + `push_secrets_vm.sh`

- **Persistance “Permission denied” sur `/var/lib/lbg/...`** :
  - s’assurer que `/var/lib/lbg/mmmorpg` appartient à `lbg:lbg`
  - redeployer rôle `mmo` (le déploiement crée/chown ces répertoires).

