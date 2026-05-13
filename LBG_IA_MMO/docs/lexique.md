# Lexique

Document **transverse** : définitions courtes des termes, acronymes et concepts utilisés dans la documentation et le code. Objectif : faciliter la **transmission** du projet (onboarding, reprise par un autre contributeur, alignement vocabulaire / code).

**Mise à jour** : enrichir ce fichier lorsqu’un nouveau concept stable apparaît dans les docs ou les ADR (voir *ADR* ci-dessous).

---

## A

**ADR** (*Architecture Decision Record*)  
Enregistrement structuré d’une **décision d’architecture** : contexte, décision adoptée, conséquences (avantages, coûts), parfois statut (brouillon, accepté, déprécié). Les ADR du dépôt vivent sous **`docs/adr/`** (ex. `0001-tronc-monorepo.md`, `0002-mmo-autorite-pont.md`, `0004-assistant-local-vs-persona-mmo.md`, `0005-new-mmo-core3-coexistence.md`). Ils complètent les plans longs (`plan_de_route.md`, `plan_fusion_lbg_ia.md`) en **figeant** un choix précis sans tout réécrire.

**Agent** (dans ce monorepo)  
Module exécuté après le routage d’intention (`lbg_agents.dispatch`), souvent derrière une **capability** déclarée (dialogue, quêtes, combat, DevOps, etc.). Peut être in-process ou exposé en **HTTP** (`/invoke`, healthz). Voir `agents/README.md`, `architecture.md`.

---

## B

**Backend**  
API FastAPI dans **`backend/`** : point d’entrée stable pour les clients (dont **`pilot_web`**), proxy vers l’orchestrateur et les health checks des agents.

---

## C

**Capability**  
Capacité déclarée dans le registry de l’orchestrateur (`CapabilitySpec`) : nom d’intention, routage vers un agent, métadonnées pour l’introspection (`GET /v1/capabilities`).

---

## F

**Fusion** (LBG_IA + LBG_IA_MMO + mmmorpg)  
Alignement progressif vers **un dépôt canonique** et un produit cohérent, décrit dans **`plan_fusion_lbg_ia.md`**. Les dépôts **`LBG_IA`** et **`mmmorpg`** servent de **sources en lecture** ; le code utile est **porté** dans ce monorepo (voir ADR **`0001-tronc-monorepo`**).

---

## I

**Intention**  
Unité logique envoyée à l’orchestrateur (souvent un libellé ou un type d’action + contexte) pour être **routée** vers la bonne capability / agent.

---

## L

**LAN** (déploiement)  
Réseau privé où tournent les VM du projet ; la répartition des rôles (IPs, variables `LBG_*`) est documentée dans **`fusion_env_lan.md`**.

**LBG_IA**  
Dépôt **source** (hors modification pour la fusion) : UI Vue, Postgres, `RouterIA`, etc. Chemin typique : `~/projects/LBG_IA/`. Voir `plan_fusion_lbg_ia.md`.

**Lyra**  
Couche « IA incarnée » : état comportemental (ex. jauges), contrats `context.lyra` / `output.lyra`, pont avec le monde. Voir **`lyra.md`**.

---

## M

**mmmorpg**  
Dépôt **source** du serveur jeu **WebSocket** (multijoueur, protocole JSON). Chemin typique : `~/projects/mmmorpg/`. À terme, code **reproduit** dans ce monorepo selon le plan de fusion. Distinct de **`mmo_server`** (HTTP, slice IA Lyra dans ce repo). (mmmorpg : Multivers Massively Multiplayer Online Role-Playing Game)

**`mmo_server/`**  
Service headless dans ce monorepo : tick monde, persistance **`WorldState`**, HTTP **`/v1/world/lyra`** pour synchroniser les jauges PNJ avec la chaîne orchestrateur / agents.

**Monorepo**  
Ce dépôt **`LBG_IA_MMO/`** : plusieurs packages (`backend/`, `orchestrator/`, `agents/`, `mmo_server/`, **`mmmorpg_server/`**, etc.) dans **un** arbre Git — **tronc** cible de la fusion (ADR 0001).

**`mmmorpg_server/`**  
Serveur **WebSocket** jeu (portage depuis le dépôt source **`mmmorpg`**) : `python -m mmmorpg_server`, variables **`MMMORPG_*`**. Voir **`mmmorpg_server/README.md`**, **`docs/mmmorpg_PROTOCOL.md`**.

**new_mmo / Core3**  
Dépôt ou clone du **serveur jeu SWGEmu (Core3)** : binaire **`core3`**, base **`swgemu`**, protocole et stack **distincts** du couple Python **`mmmorpg_server`** + **`mmo_server`**. Coexistence et migration documentées : ADR **`0005-new-mmo-core3-coexistence.md`**, guide **`migration_new_mmo_core3.md`**, emplacement clone optionnel **`third_party/new_mmo/`** (ignoré par Git).

---

## O

**Orchestrateur** (`orchestrator/`)  
Service qui reçoit une **intention**, consulte le **registry** de capabilities, applique éventuellement des fallbacks, puis déclenche les **agents**. Point central du routage IA.

---

## P

**Pilot** / **`pilot_web/`**  
Interface web de **pilotage et monitoring** (routes backend `/v1/pilot/…`, page **`/pilot/`**) : tests d’intentions, santé des services, capabilities.

**PNJ** (*personnage non joueur*)  
Entité dont le comportement et les jauges peuvent être reliés à **Lyra** et au **monde** (`mmo_server`, futur serveur jeu intégré).

---

## S

**Seed (monde)**  
Fichier JSON **`mmo_server/world/seed_data/world_initial.json`** : PNJ et temps initial lorsqu’il n’y a pas encore de **`world_state.json`** persisté. Surcharge : **`LBG_MMO_SEED_PATH`**. Voir **`world/seed_data/README.md`**.

**Strangler** (*strangler fig pattern*, « figuier étrangleur »)  
Stratégie d’intégration : faire **coexister** l’ancien et le nouveau par étapes, puis **retirer** progressivement les doublons — utilisée dans le plan de fusion (`plan_fusion_lbg_ia.md`).

---

## T

**`trace_id`**  
Identifiant de corrélation propagé dans le contexte des requêtes (pilot → backend → orchestrateur → agents) pour suivre une même chaîne dans les logs.

**Tronc** (dépôt)  
Dépôt **canonique** où vit le développement cible du produit fusionné : ici **`LBG_IA_MMO/`** (ADR 0001).

---

## V

**`verify_stack_local.sh`**  
Script **`infra/scripts/verify_stack_local.sh`** : vérifie les **`/healthz`** (backend, orchestrateur, `mmo_server`) quand la stack locale tourne — voir **`bootstrap.md`**.

---

## W

**`WorldState`**  
État persisté du monde côté **`mmo_server`** (fichier JSON, variables `LBG_MMO_*`), distinct de l’autorité **temps réel** du futur serveur jeu porté depuis **mmmorpg**.

---

## É

**État des lieux (fusion)**  
Document **`fusion_etat_des_lieux_v0.md`** : photographie phase A (routes HTTP monorepo, références **LBG_IA** / **mmmorpg**, variables de pont). À mettre à jour lors des imports majeurs de code.

---

## Voir aussi

- `adr/0001-tronc-monorepo.md` — décision tronc monorepo
- `adr/0002-mmo-autorite-pont.md` — autorité `mmmorpg` vs `mmo_server`, pont jeu ↔ IA
- `fusion_etat_des_lieux_v0.md` — inventaire réseau / env (fusion v0)
- `fusion_spec_lyra.md`, `fusion_spec_agents.md`, `fusion_spec_monde.md` — specs fusion (phase B)
- `fusion_pont_jeu_ia.md` — pont jeu ↔ IA
- `plan_de_route.md` — priorités et jalons
- `plan_fusion_lbg_ia.md` — fusion des trois lignées
- `architecture.md` — vue composants
- `vision_projet.md` — vision produit
