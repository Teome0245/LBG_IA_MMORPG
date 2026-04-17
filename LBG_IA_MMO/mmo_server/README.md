# MMO Server (headless)

Serveur de simulation headless tick-based :
- monde data-driven
- entités, factions, races, métiers
- quêtes dynamiques
- classes flexibles et combinables
- NPC gouvernés par `lyra_engine/`

## Démarrage

Voir `../../bootstrap.md`.

## Mode HTTP (sync Lyra avec le backend)

- **Local (dev)** : **`python3 -m uvicorn http_app:app --host 127.0.0.1 --port 8050`** (répertoire courant : ce dossier, **venv activé** ; sur Ubuntu sans paquet `python-is-python3`, la commande `python` n’existe pas — utiliser **`python3`** ou **`/opt/LBG_IA_MMO/.venv/bin/python -m uvicorn …`**).
- **LAN / systemd** : l’unité **`lbg-mmo-server`** démarre plutôt avec **`--host 0.0.0.0 --port 8050`** afin que le **backend** (autre machine) puisse joindre **`LBG_MMO_SERVER_URL`**.
- **`GET /healthz`**, **`GET /v1/world/lyra?npc_id=npc:smith`** — instantané des jauges PNJ (tick en thread d’arrière-plan).
- **Gameplay v1 (écriture interne, LAN)** :
  - **`POST /internal/v1/npc/{npc_id}/aid`** — applique des deltas bornés sur les jauges (`hunger/thirst/fatigue`) et la réputation, avec gate optionnel `LBG_MMO_INTERNAL_TOKEN` via `X-LBG-Service-Token`.
- Variable **`LBG_MMO_SERVER_URL`** côté backend ; contexte **`world_npc_id`** — voir `docs/lyra.md`.

## Données initiales (seed) — PNJ / scène

- Fichier versionné : **`world/seed_data/world_initial.json`** (même schéma que la sauvegarde : `schema_version`, `now_s`, liste `npcs` + jauges).
- Utilisé au **premier** démarrage lorsqu’aucun état persisté n’existe encore ; ensuite c’est **`world_state.json`** qui prime.
- **`LBG_MMO_SEED_PATH`** : chemin optionnel vers un autre JSON seed (absolu ou relatif au cwd du processus).
- Détail : **`world/seed_data/README.md`**, ADR **`docs/adr/0002-mmo-autorite-pont.md`**.

## Persistance (reprise après redémarrage)

- Fichier JSON par défaut : **`mmo_server/data/world_state.json`** (créé au premier save ; ignoré par Git sauf `.gitkeep`).
- **`LBG_MMO_STATE_PATH`** : chemin absolu (ex. `/var/lib/lbg/mmo/world_state.json` sur VM — créer le répertoire et droits **`lbg`**).
- **`LBG_MMO_SAVE_INTERVAL_S`** : intervalle mini entre sauvegardes (défaut **30** s, minimum 5).
- **`LBG_MMO_DISABLE_PERSIST=1`** : pas de chargement / sauvegarde (tests).

### Reset état (recharger le seed)

Si tu veux **forcer** le rechargement du seed (ex. après ajout de nouveaux PNJ), il faut supprimer / déplacer
le fichier d’état **pendant que le service est arrêté** (sinon la sauvegarde à l’arrêt peut le recréer).

Script dédié (LAN) :

```bash
cd LBG_IA_MMO
LBG_VM_HOST=192.168.0.245 LBG_VM_USER=lbg bash infra/scripts/reset_mmo_state_vm.sh
```

