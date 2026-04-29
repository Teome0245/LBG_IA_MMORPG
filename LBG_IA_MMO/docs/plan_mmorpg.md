# Plan MMO (Multivers) — base d’architecture

Ce document sert de **référence produit/tech** côté monorepo.

Source d’inspiration : le fichier `plan MMMORPG.md` (à la racine) est un **carnet d’idées** non contractuel ; on y pioche des suggestions, puis on les reformule ici de manière **priorisée**, **testable** et **compatible** avec l’existant.

## Vision générale

- MMORPG multivers (plusieurs planètes) avec règles physiques/tech/magie propres.
- Inspirations : Gunnm, Cyberpunk, Albator, DBZ, Discworld, Avatar, Free Guy, Firefly, Steampunk, FMA.
- Joueurs humains + joueurs IA + **MJ IA** (assistance + événements + cohérence).
- Progression possible **sans combat** : métiers, exploration, social, artisanat.

## Hypothèses techniques (cibles)

- OS serveur : Linux
- Langage : Python
- Communication : WebSocket/TCP/UDP selon besoins (Gateway)
- Stockage cible : PostgreSQL + Redis (cache) — à introduire plus tard
- Client : Godot Engine (rendu sphérique + UI)

## Monde / multivers

- Planètes :
  - **Terre1** : sphérique “standard”
  - **Terre plate** : exception
- Cycles :
  - Jour/nuit : **6 heures**
  - Orbite : **91 jours (±1)**
  - Lunes : marées, transformations, événements
- Contraintes possibles par planète : saisons, techno, physique, magie

## Races / factions / civils

- **3 factions principales** dont **1 neutre**
- Majorité **civile** (objectif : ~75% du monde), avec opinions/réputation
- Races jouables + races civiles, systèmes de langages possibles

## Professions (SWG pre‑CU-like)

- Professions modulaires, progression par usage
- Interdépendance entre métiers
- Artisanat complexe, ressources dynamiques, économie joueur/PNJ

## IA & PNJ

PNJ “vivants” attendus :
- background individuel
- objectifs personnels
- cycle de vie + routines quotidiennes
- réactions à l’environnement et à la réputation

Architecture IA proposée :
- GOAP (planning objectifs/actions)
- Behavior Trees (réactivité)
- Scheduler (routines/horaires/événements)

### PNJ “vivants” — extension incrémentale (sans tout chambouler)

Objectif : obtenir l’illusion d’une société persistante (style SWG / Free Guy) **sans** faire tourner une IA “complète” pour tous les PNJ en permanence.

#### 3 niveaux de simulation (LOD)

- **Niveau 1 — PNJ actifs (proches du joueur / zone chargée)** :
  - simulation détaillée (déplacements, interactions, réactions)
  - arbre de comportement + actions “atomiques”
  - budget strict (CPU/LLM) par tick
- **Niveau 2 — PNJ semi-actifs (même région, hors champ immédiat)** :
  - simulation simplifiée (routines approximées, interactions rares)
  - pas de pathfinding coûteux (ou très limité)
- **Niveau 3 — PNJ passifs (hors région)** :
  - simulation statistique/agrégée (économie macro, vieillissement, natalité/mortalité, événements)
  - aucun dialogue “en direct”

#### “Ticks sociaux” (cadence de simulation)

Principe : simuler à des fréquences différentes selon le niveau.

- **Passifs** : 1 tick toutes les 5–30 minutes (configurable)
- **Semi-actifs** : 1 tick toutes les 10–30 secondes (configurable)
- **Actifs** : tick temps réel (ou sous-tick) dans la boucle de zone

#### Modèle de données PNJ (minimal puis extensible)

À viser en premier : un schéma stable, même si le contenu est “stub”.

- **Identité** : `npc_id`, nom, race, âge, traits, appartenance (faction/civil), langue(s)
- **Situation** : lieu/région, logement, profession, inventaire/ressources (macro)
- **État** : besoins (via Lyra : faim/soif/fatigue…), santé, humeur/ton
- **Objectifs** :
  - court/moyen/long terme (même représentés par des tags au début)
  - “intentions” activables par le moteur (ex. chercher stock, demander aide, fuir)
- **Relations** : liens + réputation locale (graphe simplifié, borné)
- **Historique** : quelques événements marquants (liste bornée)

#### Cycle de vie (version “serveur”)

Au départ, tout peut rester statistique (pas besoin de “graphique”).

- Naissance → enfance → adulte → vieillesse → mort
- Remplacement/succession : transfert de certains attributs (logement, profession, réputation)
- Contraintes : bornes et quotas pour éviter l’explosion de population

#### Routines dynamiques

Base : “routine planifiée” + perturbations par événements.

- lever / manger / travailler / socialiser / dormir
- adaptation simple :
  - stock vide → chercher fournisseur
  - danger/crime → alerte/éviter zone
  - crise → changer temporairement de routine

#### Économie vivante (progressive)

- PNJ comme acteurs : produire/consommer/échanger
- Prix influencés par : rareté, distance, risques, factions, événements
- Version 1 : flux “macro” (Niveau 3) + quelques PNJ “actifs” de commerce

#### Événements dynamiques

Catalogue (à injecter via `EventEngine`) :
- crimes, catastrophes, guerres, famines, migrations, épidémies, révoltes, découvertes

Règle d’implémentation : un événement est un objet persistant (début/fin, scope, effets) qui modifie objectifs/routines/économie, pas un “script one-shot” perdu dans le code.

#### MJ IA (cadre, sans dépendance obligatoire au LLM)

Le MJ IA peut être introduit en **deux couches** :
- **MJ déterministe** (règles) : cohérence, déclenchements, garde-fous
- **MJ génératif (LLM, optionnel)** : narration, variantes, quêtes “flavor”

#### Intégration monorepo (cohérence avec l’existant)

Sans refonte : brancher ces concepts sur les briques déjà en place.

- **Monde** : `mmo_server` (autorité monde “Lyra/read model” côté HTTP)
- **Temps réel** : `mmmorpg_server` (WS, gameplay joueur, commit/snapshot)
- **IA/Agents** : orchestrateur + agents (dialogue/quêtes/combat/devops)
- **Contrat minimal recommandé** :
  - le monde expose un “snapshot PNJ” (LOD3/LOD2) + “focus PNJ” (LOD1) à la demande
  - l’IA renvoie des sorties bornées (ex. `world_flags`, `quest_state`, “intentions”) déjà filtrées côté pont WS

### Réputation locale PNJ — v1 (design)

Objectif : un **premier système de réputation très simple**, stocké côté monde et visible dans les snapshots, sans changer le gameplay existant.

- **Portée** : réputation **par PNJ** (ou petit groupe local), pas encore par grande faction globale.
- **Stockage** (v1 implémenté, minimal) :
  - côté `mmo_server` : champ **`Npc.reputation_value`** (int borné \([-100, 100]\), persisté dans `WorldState`).
  - côté `mmmorpg_server` : map interne **`npc_reputation[npc_id]`** (int borné, persistée dans `state.json` avec `schema_version=2`).
  - côté snapshot Lyra : miroir **`lyra.meta.reputation.value`** (int) pour le PNJ ciblé.
  - (vision plus tard) : tags/labels (`reputation.tags`) — **hors v1**.
- **Sources de variation (v1)** :
  - actions déjà présentes dans le système : acceptation/réussite/échec de quêtes, certains commits (`world_flags`) ;
  - règles simples, par exemple :
    - +10 à l’acceptation d’une quête clé,
    - +X à la réussite, −Y à l’abandon ou au refus explicite,
    - bornage dur : la valeur reste entre −100 et +100.
- **Consommation** :
  - les agents (dialogue/quêtes) peuvent simplement **lire** cette valeur/tag pour adapter le ton ou débloquer du texte supplémentaire, sans logique serveur complexe.
- **État actuel (implémenté)** :
  - `mmo_server` expose déjà `lyra.meta.reputation.value` (défaut 0) via `/v1/world/lyra`.
  - Le snapshot interne `mmmorpg_server` expose `lyra.meta.reputation.value` (persisté côté serveur WS) ; un commit `reputation_delta` peut faire évoluer la valeur (bornée).
  - **Double-write (cohérence fallback)** : après un commit `reputation_delta`, le backend tente aussi d’appliquer le delta sur `mmo_server` via `POST /internal/v1/npc/{npc_id}/reputation` (best-effort) pour que le fallback `meta.source=mmo_world` reste aligné avec l’état “jeu WS”.
  - **Auth optionnelle** : si `LBG_MMO_INTERNAL_TOKEN` est défini sur **245** (`lbg-mmo-server`), l’endpoint interne exige `X-LBG-Service-Token` ; le **backend 140** doit avoir la **même** valeur (`LBG_MMO_INTERNAL_TOKEN`) pour relayer le double-write.
  - **Pilot (debug)** : `POST /v1/pilot/reputation` (sans LLM) + gate optionnel `LBG_PILOT_INTERNAL_TOKEN` ; smokes LAN dédiés (`smoke_reputation_*`, `smoke_pilot_reputation_auth_lan.sh`, `smoke_mmo_internal_reputation_auth_lan.sh`).
- **Non-objectifs v1** :
  - pas encore de réputation globale par ville/faction,
  - pas de propagation automatique entre PNJ (pas de “gossip system”),
  - pas de changement d’aggro/combat : la réputation reste un **signal narratif** pour le moment.

## Quêtes dynamiques

QuestEngine (cible) :
- templates + générateur + tracker
- entrées : état du monde, position/skills du joueur, faction/réputation
- sorties : quêtes instanciées et persistées

## Modules serveur (cible)

Découpage logique proposé (à faire converger avec `mmo_server/`) :
- WorldCore (planètes, cycles, saisons)
- EntityEngine (joueurs/PNJ)
- FactionSystem (réputation/diplomatie)
- MagicEngine / TechEngine
- PhysicsEngine (vol, nage, gravité, transformations lunaires)
- EventEngine (événements dynamiques)
- AIEngine (PNJ + MJ IA)
- EconomyEngine / HousingEngine
- NetworkLayer (gateway + protocol)

## MMO v1 (LAN) — périmètre acté

Cette section fige ce que couvre **MMO v1** sur le LAN (3 VM) avec l’infra actuelle. Tout le reste du plan reste une **vision** pour des itérations ultérieures.

### Ce qui est déjà en place (v1)

- **Monde / état** :
  - `mmo_server` : boucle monde headless + HTTP (`/healthz`, `/v1/world/lyra`) sur la VM MMO.
  - Persistance JSON atomique (`WorldState`, `LBG_MMO_STATE_PATH`, `LBG_MMO_SAVE_INTERVAL_S`) + script de reset seed (`reset_mmo_state_vm.sh`).
  - Seed monde `world/seed_data/world_initial.json` avec un petit ensemble de PNJ (`npc:innkeeper`, `npc:guard`, `npc:scribe`, `npc:mayor`, `npc:healer`, `npc:alchemist`) testé via les smokes LAN.
- **Serveur WS temps réel** :
  - `mmmorpg_server` porté dans le monorepo : WebSocket **7733**, protocole défini dans `docs/mmmorpg_PROTOCOL.md`.
  - HTTP interne `mmmorpg_server` (`/healthz`, `/internal/v1/npc/{npc_id}/lyra-snapshot`, `dialogue-commit`) avec auth + rate-limit (voir `docs/ops_pont_interne_auth_rl.md`).
- **Ponts IA ↔ monde** :
  - Pont **lecture** : backend consomme le snapshot Lyra via `LBG_MMMORPG_INTERNAL_HTTP_URL` et enrichit `context.lyra` / `lyra_meta` pour `/v1/pilot/route`.
  - Fallback monde : si snapshot interne KO, backend bascule sur `mmo_server` (`meta.source=mmo_world`).
  - Pont **écriture** : `/v1/pilot/route` peut produire un `commit` vers `mmmorpg_server` (flags en whitelist) ; validation via smokes `smoke_mmmorpg_commit.sh` et `smoke_commit_dialogue*.sh`.
  - Écriture **directe (debug/ops)** : `POST /v1/pilot/reputation` applique un `reputation_delta` sans LLM (token optionnel `LBG_PILOT_INTERNAL_TOKEN`) + double-write `mmo_server` (voir section réputation).
  - **Gameplay v1 (monde, écriture interne)** : `mmo_server` expose `POST /internal/v1/npc/{npc_id}/aid` (deltas jauges + réputation, bornés) pour une interaction joueur→monde déterministe, testable et persistée.
- **Smokes et observabilité** :
  - Smokes LAN par rôle : `smoke_vm_lan.sh`, `smoke_lan_minimal.sh`, `smoke_lan_quick.sh` (VM + monde + pont interne + internal route sans LLM).
  - Smokes spécifiques : snapshot auth/RL, bridge WS→Lyra, pilot route Lyra meta, WS→IA final-only JSON, commit (accepté/rejeté).
  - Traçage `trace_id` bout-en-bout (WS→backend→snapshot).
  - UX WS “placeholder remplacé” : le pont IA envoie un placeholder `world_tick.npc_reply` **avec le même `trace_id`** que la réponse finale, afin qu’un client puisse remplacer la bulle (voir `infra/scripts/smoke_ws_hello_llm_aid_lan.sh`).

### Notes ops (persistance)

- `mmmorpg_server` peut persister son état commits dans `MMMORPG_STATE_PATH` (défaut LAN : `/var/lib/lbg/mmmorpg/state.json`).
- Sur les VM, il faut que les répertoires `/var/lib/lbg/mmmorpg` (et `/var/lib/lbg/mmo` si utilisé) soient **créés** et **écrits par l’utilisateur de service** (souvent `lbg`).

### Urbanisme & Physique (Correctifs v1.1)

- **Échelle du Village** : 
    - Logique/Serveur : 1 tuile = 2m.
    - Rendu Client : 8px = 1m (Personnages/Logic).
    - **Rendu Image (PNG)** : 16px = 1m (32px par tuile de 2m). L'image du village (1680x1360) doit être affichée avec un multiplicateur de 2 par rapport à l'échelle logique pour un alignement parfait.
- **Bouclage du Monde (World Wrap)** :
    - Horizontal (X) : Bouclage à ±51200m (Total 102.4km).
    - Vertical (Z) : Clamp à ±25600m.
    - **Interpolation Client** : Doit être "Wrap-aware" (Shortest Path) pour éviter les sauts visuels lors de la traversée de la limite Est/Ouest.
- **Mouvement & Bobbing** :
    - Le sautillement de marche (bobbing) est stabilisé avec un seuil de vitesse (>0.5m/s) pour éviter les micro-vibrations sur les coordonnées positives.

### Ce qui est hors v1 (assumé pour plus tard)

- **Factions complètes** (philo, gameplay, réputation globale multivers) : même si les factions sont définies dans le plan de vision, v1 se contente d’un monde unique avec quelques PNJ “génériques”.
- **Professions SWG-like** complètes : pas encore de système de professions jouables (arbre de skills, progression par usage, interdépendances), seulement des stubs côté quêtes/combat.
- **Économie systémique** (PNJ producteurs/consommateurs, prix émergents, routes commerciales) : v1 limite l’économie à des flags simples (`world_flags`).
- **Housing joueur** (parcelles, constructions, propriété persistée) : hors périmètre v1.
- **Vol atmosphérique / nage / planètes multiples** : `mmmorpg_server` expose une planète simple + tick temps ; les autres couches physiques restent à faire.
- **MJ IA “riche”** (événements dynamiques générés, arcs narratifs complexes) : v1 se limite à des smokes et à quelques quêtes pilotées par agents.

### Règle d’évolution à partir de v1

- Toute nouvelle feature MMO doit être rattachée à ce périmètre v1 par une phrase simple :
  - soit **“extension v1”** (ex. un nouveau type de PNJ dans le seed, un nouveau flag `world_flags` supporté par le commit),
  - soit **“préparation v2+”** (ex. début de système de factions ou de professions, clairement signalé comme expérimental).


