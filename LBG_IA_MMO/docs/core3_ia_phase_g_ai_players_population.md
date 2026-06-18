# Phase G — Population de joueurs IA

**Objectif** : peupler Serveur Prime avec plusieurs **joueurs IA** (en plus des PNJ), pilotés par l'orchestrateur et le sidecar Core3.

## Principe

Les joueurs IA sont déclarés dans un registre data-driven :

`content/core3/core3_ia_players.json`

Chaque entrée décrit :

- compte Core3
- personnage / prénom IG
- `actor_id` orchestrateur
- métier courant (`profession_current`)
- métier dynamique (`profession_dynamic=true`)
- session `core3client`
- fichier env secret
- unité systemd
- capabilities disponibles

Les métiers ne sont **pas fixes** : `profession_current=scout` pour Nix signifie seulement “état courant”.

## Joueurs actuels

| ID | Compte | Personnage | Métier courant | Service |
|----|--------|------------|----------------|---------|
| `lia` | `Bot_IA` | `Lia Bot` | orchestrator | `lbg-core3-ia-bot-client` |
| `nix` | `Bot_IA_2` | `Nix Bot` | scout | `lbg-core3-ia-bot-client-nix` puis template `lbg-core3-ia-player@nix` |

## Snapshots multi-joueurs

Le screenplay écrit maintenant :

```text
ia_bridge/player_snapshots.json
```

Le sidecar lit ce fichier en priorité pour :

```bash
curl -s 'http://127.0.0.1:8791/v1/player-snapshot?player=Nix'
```

Fallback conservé : ancien `player_snapshot.json` mono-joueur Lia.

## Installer un joueur IA

Pour un joueur déjà déclaré dans `core3_ia_players.json` :

```bash
bash infra/scripts/install_core3_ia_player_vm.sh nix
```

Puis renseigner le secret sur la VM 245 :

```bash
nano /opt/lbg-new-mmo-clean/MMOCoreORB/bin/.env-core3client-nix
chmod 600 /opt/lbg-new-mmo-clean/MMOCoreORB/bin/.env-core3client-nix
```

Activation template :

```bash
sudo systemctl enable --now lbg-core3-ia-player@nix
```

Le service spécifique historique reste possible :

```bash
sudo systemctl enable --now lbg-core3-ia-bot-client-nix
```

## Ajouter un nouveau joueur IA

1. Créer le compte Core3.
2. Créer le personnage en jeu.
3. Récupérer `character_oid` en base.
4. Ajouter une entrée dans `core3_ia_players.json`.
5. Ajouter `content/core3/ia_bridge/<id>_bot_session.json`.
6. Ajouter `infra/snippets/.env-core3client-<id>.example`.
7. Installer :

```bash
bash infra/scripts/install_core3_ia_player_vm.sh <id>
```

## Actions

Toutes les commandes `pending.jsonl` acceptent déjà `player=<firstname>` :

```bash
curl -s -X POST http://192.168.0.245:8791/v1/enqueue \
  -H 'Content-Type: application/json' \
  -d '{"action":"perform","player":"Nix","message":"forage"}'
```

Actions communes :

- `say`
- `perform`
- `interact`
- `approach_player`
- `move_to`

## Autonomie générique

Depuis la Phase H, l'autonomie lit aussi les événements sociaux récents. Voir `docs/core3_ia_phase_h_social_perception.md`.

Nix est le premier joueur IA branché sur la boucle générique :

```bash
sudo systemctl enable --now lbg-core3-ia-player-autonomy@nix
```

Variables du template :

| Variable | Défaut | Rôle |
|----------|--------|------|
| `LBG_CORE3_IA_PLAYER_ID` | `%i` | ID registre (`nix`, futur `mira`, etc.) |
| `LBG_CORE3_PLAYER_AUTONOMY_ENABLED` | `1` | Active la boucle |
| `LBG_CORE3_PLAYER_AUTONOMY_INTERVAL_S` | `35` | Intervalle de décision |
| `LBG_CORE3_PLAYER_AUTONOMY_MODE` | `orchestrator` | Passe par `/v1/route` (`sidecar` possible pour debug) |
| `LBG_CORE3_IA_SIDECAR_URL` | `http://127.0.0.1:8791` | Sidecar local VM 245 |
| `LBG_ORCHESTRATOR_URL` | `http://192.168.0.140:8010` | Orchestrateur VM 140 |

Le moteur est `agents/src/lbg_agents/core3_player_autonomy.py` et adapte le prompt au `profession_current`. En mode `orchestrator`, il poste sur `/v1/route` avec :

```json
{
  "core3_action": {
    "kind": "player_think",
    "player": "Nix",
    "enqueue": true
  },
  "core3_player_id": "nix",
  "core3_autonomy": true
}
```

Déclenchement manuel côté orchestrateur :

```bash
curl -s -X POST http://127.0.0.1:8010/v1/core3/players/nix/tick \
  -H 'Content-Type: application/json' \
  -d '{"via":"sidecar"}'
```

## Limites MVP

- Les radials natifs SWG (trade/groupe/duel réels) restent à brancher.
- L'autonomie générique v1 passe par le routage orchestrateur pour les services, avec une route de debug en sidecar direct.

## Joueurs IA = vrais joueurs (pas ancres PNJ)

Les bots **ne servent pas** à maintenir des PNJ en ligne. Ce sont des **personnages joueurs** avec :

- progression métier sur **cycles longs** (apprentissage → maîtrise → pratique → oubli progressif → transition) ;
- implication **économie** (forage, vente, achat comptoir) ;
- implication **sociale** (say, greet, assist) ;
- **quêtes** et objectifs `progression_goals` ;
- **état individuel** : pas de conscience collective, cohérence via registre + profils comportementaux.

Fichiers :

| Fichier | Rôle |
|---------|------|
| `content/core3/core3_profession_lifecycle.json` | Durées de phase, tags scènes par métier |
| `ia_bridge/player_profession_state.json` | État persistant par joueur (`lia`, `nix`, `mira`, …) |
| `agents/.../core3_profession_lifecycle.py` | Machine à états + biais de scène |

Chaque tick d'autonomie appelle `tick_player_lifecycle()` : le métier **actif** (`focus_profession`) pilote les scènes (danse, forage, trainer, commerce).

## Roadmap population (10 → 100 bots)

Objectif : répartition des rôles et métiers sur les **factions**, sans multiplier les ancres.

| Palier | Cible | Prérequis |
|--------|-------|-----------|
| **v1** | 3 bots (Lia, Nix, Mira) | Cycles métier, autonomie, snapshots multi-joueurs |
| **v2** | 10 bots | Template `lbg-core3-ia-player@`, registre `core3_ia_players.json`, quotas systemd |
| **v3** | 20–50 bots | Répartition `faction_id` + `profession_current` dans le registre, anti-collision noms |
| **v4** | 50–100 bots | Orchestrateur shardé, LLM batch, économie/quêtes data-driven |

Ajouter un bot : une entrée registre + compte Core3 + `install_core3_ia_player_vm.sh` — **aucune** dépendance « ancre » vers un PNJ pilote.

## Déploiement après rebuild Prime

Quand la compilation `core3-clean` est terminée :

```bash
# 1. Lua + sidecar + agents
LBG_NEW_MMO_VM_HOST=192.168.0.246 bash infra/scripts/deploy_core3_ia_bridge_vm.sh --restart
rsync -az agents/src/ lbg@192.168.0.246:/opt/LBG_IA_MMO/agents/src/

# 2. Privilèges GM Lia (Bot_IA → admin_level 1)
ssh lbg@192.168.0.246 'bash /opt/LBG_IA_MMO/infra/scripts/apply_ia_account_roles_vm.sh'

# 3. Bot #4 Kael (apres creation compte/perso IG)
bash infra/scripts/install_core3_ia_player_vm.sh kael --enable

# 4. Reconnecter tous les bots
ssh lbg@192.168.0.246 'bash /opt/LBG_IA_MMO/infra/scripts/run_ensure_ia_bots.sh'
```

Modules ajoutés (v1) :

| Module | Rôle |
|--------|------|
| `core3_quest_autonomy.py` | `progression_goals` → quêtes accept/turnin |
| `core3_economy_loop.py` | forage → craft → vente par phase lifecycle |
| `skill_forget` (Lua) | stub oubli métier en phase `decay` |
| spawn `BuildingObject` | Jax barman si joueur en cantina |
