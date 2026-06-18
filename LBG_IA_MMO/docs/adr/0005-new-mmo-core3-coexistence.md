# ADR 0005 — Dépôt **new_mmo** (Core3 / SWGEmu) : coexistence avec la stack MMO Python

## Statut

**Accepté** — 2026-05-12  
**Amendé** — 2026-06-28 : **Core3 Prime = serveur jeu unique** ; bac à sable Python (`mmo_server`, `mmmorpg_server`) **gelé** — voir [`docs/ARCHIVED_mmmorpg_sandbox.md`](../ARCHIVED_mmmorpg_sandbox.md).

## Contexte

Le monorepo **`LBG_IA_MMO/`** embarque aujourd'hui deux briques **Python** complémentaires pour le MMO « slice IA + bac à sable » :

- **`mmo_server/`** : HTTP (ex. Lyra PNJ, `WorldState`), consommée par le **backend** et la chaîne agents / pilot.
- **`mmmorpg_server/`** : WebSocket jeu, protocole et persistance côté **bac à sable** documentés dans l'écosystème LBG_IA_MMO.

Le dépôt **`new_mmo`** (workspace typique : `~/projects/new_mmo`) contient un **autre moteur serveur** : binaire **`core3`**, arborescence **Core3 / MMOCoreORB**, base **MariaDB `swgemu`**, écosystème **SWGEmu**. Il est déjà exploité en parallèle sur des VMs LAN (ex. **192.168.0.245**) sans être **référencé** ni **cadré** dans le monorepo Git.

Sans décision explicite, on risque :

- confusion entre **« serveur MMO Python »** et **« serveur jeu Core3 »** dans les discussions et runbooks ;
- tentatives de **remplacement plug-and-play** (même port / même protocole) **impossibles** sans refonte des clients et des ponts IA ;
- absence de **piste documentée** pour une migration progressive.

## Décision (2026-05-12 — historique)

1. **`new_mmo` est une quatrième lignée « source / runtime »** pour le **serveur jeu Core3**, **distincte** de `mmmorpg` (Python) et de `mmo_server` (HTTP slice IA), jusqu'à migration éventuelle planifiée.

2. **Intégration Git immédiate** : on **ne merge pas** l'arbre Core3 dans la racine du monorepo. La référence canonique documentée est :
   - clone voisin **`~/projects/new_mmo`**, **et/ou**
   - répertoire local **`LBG_IA_MMO/third_party/new_mmo/`** (contenu **non versionné** — voir `third_party/README.md`).

   Un **`git submodule`** vers l'URL officielle du dépôt `new_mmo` reste **optionnel** (équipe, CI, taille du clone) ; la procédure est décrite dans **`docs/migration_new_mmo_core3.md`**.

3. **Remplacement « entier » de la partie serveur MMO Python** par Core3 est **hors scope tacite** : c'est un **programme de migration** (phases, contrats, clients, env, systemd) décrit dans **`docs/migration_new_mmo_core3.md`**.

4. **Cohabitation** : sur une même VM (ex. 245), **Core3** et les services Python peuvent coexister **si** ports, ressources et procédures d'exploitation sont **documentés** (pas de double écriture « monde » implicite sans pont — alignement d'esprit avec **ADR 0002**).

5. **ADR 0002** : jusqu'à la bascule prod, autorité jeu = **`mmmorpg_server`** ; **amendement juin 2026** — bascule **effectuée** : autorité jeu = **Core3 Prime** (voir ADR 0002).

## Amendement — 2026-06-28 (bascule prod, gel Python)

**Contexte** : Core3 Prime tourne en production sur VM **246** (galaxie 3, login **44553**). Le bac à sable Python (v1 LAN sur VM 245) a rempli son rôle de prototype pont IA ↔ monde.

**Décisions complémentaires** :

1. **Serveur jeu cible unique** : **Core3 Prime** — toute nouvelle feature **gameplay** se fait dans le fork `new_mmo` / `content/core3/`, pas dans `mmmorpg_server` ni `mmo_server`.

2. **Bac à sable Python gelé** : `mmo_server` + `mmmorpg_server` + `web_client` + `lbg_client_godot` restent dans le repo en **lecture** ; **pas de nouvelle feature** ; doc d'archivage : [`ARCHIVED_mmmorpg_sandbox.md`](../ARCHIVED_mmmorpg_sandbox.md).

3. **Client joueur** : **client SWGEmu personnalisé** (launchpad dual PreCU/Prime, patches `.tre`) — pas Godot ni `web_client` comme axe produit.

4. **`deploy_vm.sh` rôle `mmo`** : reste disponible pour **maintenance legacy** et smokes ; **non requis** pour l'expérience joueur Prime.

5. **Orchestrateur / agents Python** : **reste actif** — pont IA via sidecar `:8791`, jobs, `core3_bot_action`, pas comme serveur jeu.

## Conséquences

### Positives

- **Vocabulaire partagé** : « MMO Python » vs « Core3 / new_mmo ».
- **Traçabilité** : un fichier de migration et ce ADR servent de **porte d'entrée** pour toute évolution d'infra ou de client.
- **Focus produit** : un seul moteur jeu en développement actif (Core3).

### Négatives / dette

- **Double stack** possible sur une VM : charge ops, discipline ports/DB (legacy 245).
- **Submodule** : discipline de versionnage et CI à renforcer si adopté.
- **Code Python conservé** : maintenance minimale tant qu'il reste dans le repo.

### Mesures de suivi

- Toute PR qui **déplace** des ports MMO ou **désactive** `mmmorpg` / `mmo_server` doit **mettre à jour** `docs/migration_new_mmo_core3.md` et, si la décision structurelle change, **ce ADR** ou un ADR fils.
- `docs/plan_fusion_lbg_ia.md` : tableau des dépôts mis à jour pour inclure **`new_mmo`**.
- Nouvelle feature gameplay → **Core3** ou pont IA, pas bac à sable Python.

## Références

- `docs/migration_new_mmo_core3.md` — plan de migration et matrice des contrats.
- `docs/adr/0001-tronc-monorepo.md` — tronc unique.
- `docs/adr/0002-mmo-autorite-pont.md` — autorité monde Python vs slice IA (amendé juin 2026).
- `docs/plan_fusion_lbg_ia.md` — vision fusion multi-lignées.
- `docs/ARCHIVED_mmmorpg_sandbox.md` — gel bac à sable Python (juin 2026).
