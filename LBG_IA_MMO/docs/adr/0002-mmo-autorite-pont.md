# ADR 0002 — Autorité monde : `mmmorpg` vs `mmo_server` et pont jeu ↔ IA

## Statut

**Accepté** — 2026-04-12

## Contexte

Deux briques coexistent dans la vision produit (voir `plan_fusion_lbg_ia.md` §3.4, `fusion_etat_des_lieux_v0.md`) :

- **`mmo_server/`** (monorepo) : HTTP, tick léger, **`GET /v1/world/lyra`**, persistance fichier **`WorldState`**, rôle **slice IA** — jauges PNJ pour dialogue / orchestrateur / agents.
- **`mmmorpg`** (dépôt source, à porter) : **WebSocket**, autorité **multijoueur** (positions, `world_tick`, entités réseau), protocole `PROTOCOL.md`.

Sans décision explicite, on risque **deux vérités** pour le même PNJ (état Lyra vs état jeu) ou des écritures concurrentes non définies.

## Décision

1. **Autorité jeu (temps réel, multijoueur)** : à terme, le **serveur porté depuis `mmmorpg`** (dans le monorepo) est la **source de vérité** pour tout ce qui relève du **monde partagé** : joueurs, entités synchronisées, tick réseau, règles de déplacement / combat côté serveur jeu.

2. **Rôle de `mmo_server` pendant la coexistence** : **`mmo_server`** reste le **service IA monde** — exposition des jauges / contexte Lyra PNJ pour la chaîne backend ↔ orchestrateur ↔ agents. Il **ne remplace pas** le serveur WS ; il peut **dériver** temporairement un état PNJ pour l’IA tant que le **pont** avec `mmmorpg` n’existe pas.

3. **Pas de double écriture sans contrat** : tant que les deux stacks tournent, **aucun** composant ne doit **écrire** dans les deux mondes sans règle documentée. Les écritures côté **`mmo_server`** restent confinées à la **simulation locale** (tick, persistance `WorldState`) ; les écritures côté **`mmmorpg`** restent dans le **jeu** une fois intégré.

4. **Pont jeu ↔ IA (cible)** : introduction **progressive** par **lecture** puis **commandes autorisées** :
   - **Phase 1** : le backend / orchestrateur consomme **`/v1/world/lyra`** (ou équivalent) pour enrichir `context.lyra` ; le jeu, une fois branché, peut **lire** un état exporté ou des **snapshots** alignés sur les `entity_id` / `npc_id` stables.
   - **Phase 2** : **événements** ou **API interne** (HTTP sur LAN, ou extension du protocole) pour **réconcilier** PNJ : par ex. dialogue IA qui **propose** une mise à jour appliquée **seulement** si le serveur jeu valide (file d’événements, idempotence, `trace_id`).

5. **Données initiales PNJ / scène** : la **liste des PNJ** et paramètres **seed** vivent dans le **monorepo** (fichiers versionnés sous `mmo_server`, voir `world/seed_data/`) pour rester **reproductibles** ; la convergence avec l’autorité **`mmmorpg`** se fera par **même identifiants** (`npc_id`) et migration de chargement lors du pont.

## Conséquences

### Positives

- Frontière claire : **jeu = WS** (futur intégré), **IA PNJ slice = `mmo_server`** jusqu’à pont.
- Évite un big bang : **coexistence** documentée, strangler pour unifier.

### Négatives / dette

- **Synchronisation** : tant que le pont n’existe pas, l’état PNJ « IA » et l’état « jeu » peuvent **diverger** — acceptable en phase de R&D si les démos ciblent soit l’IA soit le jeu seul.
- **Travail restant** : sous-système d’événements ou d’API de réconciliation (hors périmètre de ce ADR).

### Mesures de suivi

- Toute nouvelle route ou variable qui **écrit** « monde » depuis l’IA doit être **revue** au regard de ce ADR.
- Mettre à jour ce document si l’autorité unique est **fusionnée** (ex. un seul processus serveur jeu + module Lyra intégré).

## Références

- `docs/plan_fusion_lbg_ia.md` — §3.4, phases B–C.
- `docs/fusion_etat_des_lieux_v0.md` — inventaire réseau.
- `docs/adr/0001-tronc-monorepo.md` — tronc monorepo.
- `mmmorpg/docs/PROTOCOL.md` (dépôt source, lecture).
