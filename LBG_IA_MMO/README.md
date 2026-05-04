# LBG_IA_MMO

Framework modulaire pour orchestrer des agents IA (locaux + API), piloter un monde MMORPG dynamique, et exécuter une simulation headless distribuée.

## Structure

- `backend/`: API FastAPI (contrats typés, services découplés, tests).
- `orchestrator/`: orchestrateur multi-agents (registry, router, introspection, fallback).
- `agents/`: stubs d’agents invoqués après routage (`lbg_agents.dispatch`).
- `mmo_server/`: moteur de simulation MMORPG headless (world, entities, quests, lyra_engine).
- `mmmorpg_server/`: serveur **WebSocket** temps réel (entités, collisions village, pont IA ↔ jeu, commits dialogue).
- `pilot_web/`: UI minimale de pilotage (servie par le backend sous `/pilot/`), build MMO statique sous `/mmo/`.
- `web_client/` (à la racine du workspace Git parent, ex. `LBG_IA_MMORPG/web_client/`): client MMO **Vite** (canvas, HUD, chat PNJ) ; sortie build synchronisable vers `pilot_web/mmo/`.
- `infra/`: Docker, systemd, scripts, configuration ; secrets locaux **`infra/secrets/lbg.env`** (non versionné, voir `lbg.env.example`) ; pilot sur VM front : **`infra/scripts/install_nginx_pilot_110.sh`** + **`infra/nginx/pilot_web_110.conf.example`**.
- `docs/`: documentation et schémas.

## Secrets (clés API)

Fichier unique **hors dépôt** : `infra/secrets/lbg.env` (voir `infra/secrets/lbg.env.example`). Ne pas committer (`.gitignore`).

**Dev local** — depuis `LBG_IA_MMO/` :

```bash
set -a && source infra/secrets/lbg.env && set +a
```

Puis lancer orchestrator, backend, agent dialogue, etc.

**Production**

1. Renseigner `infra/secrets/lbg.env` (copie depuis l’exemple ou ton poste de travail), ajuster les URLs `LBG_*` pour la VM si besoin.
2. Pousser vers les VM : `bash infra/scripts/push_secrets_vm.sh`  
   (par défaut **les trois** hôtes LAN : `LBG_LAN_HOST_CORE` / `MMO` / `FRONT` → 140 / 245 / 110 ; installe `/etc/lbg-ia-mmo.env`, droits **`640` `root:lbg`**, puis redémarre les `lbg-*` présents sur chaque machine).  
   Une seule cible : `LBG_VM_HOST=192.168.0.140 bash infra/scripts/push_secrets_vm.sh`. Liste explicite : `LBG_VM_HOSTS="… … …"`.  
   Autres variables : `LBG_VM_USER` (défaut **`lbg`**), `LBG_SECRETS_GROUP`, `LBG_SECRETS_FILE`. Compte VM : `docs/ops_vm_user.md`.
3. Déployer le code : `bash infra/scripts/deploy_vm.sh` — les unités systemd chargent `EnvironmentFile=-/etc/lbg-ia-mmo.env`.  
   Pour enchaîner déploiement + secrets : `LBG_PUSH_SECRETS=1 bash infra/scripts/deploy_vm.sh` (si `infra/secrets/lbg.env` existe).

Modèle sans secrets : `infra/secrets/lbg.env.example`.

## Démarrage rapide

Consultez `../bootstrap.md` (à la racine du workspace) pour l’installation, l’exécution locale, Docker, et systemd.

## Documentation

Dans `docs/` :
- `docs/architecture.md` : vue d’ensemble technique
- `docs/subagents_cursor.md` : sous-agents Cursor (rôles, invocation, conventions)
- `docs/vision_projet.md` : vision produit (orchestrateur + agents + auto-évolution + MMO)
- `docs/lyra.md` : spécification Lyra 2.0 (jauges, intégrations)
- `docs/plan_mmorpg.md` : plan d’architecture serveur MMO multivers
- `docs/plan_de_route.md` : priorités 0–3, fusion LBG_IA, suivi des jalons
- `docs/carte_plan_global.md` : alignement plan large (`.cursor/rules`) ↔ modules réels et backlog
- `docs/plan_fusion_lbg_ia.md` : fusion progressive (**LBG_IA**, **`~/projects/mmmorpg`**, ce monorepo — phases, tronc, pont MMO)
- `docs/fusion_env_lan.md` : **IPs 140 / 245 / 110**, variables `LBG_*`, `deploy_vm.sh`, option front sur 110
- `docs/ops_devops_audit.md` : VM — audit DevOps JSONL (logrotate), rotation du jeton d’approbation
- `docs/ops_vm_user.md` : compte **`lbg`** (sudoer, SSH, services systemd)

