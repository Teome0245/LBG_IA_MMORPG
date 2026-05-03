# Carte : plan global (`.cursor/rules`) ↔ monorepo réel

Pour la **priorisation produit « poste d’abord, puis MMO, puis évolution contrôlée »**, voir **`docs/plan_de_route.md`** — section **« Étoile du nord produit (priorisée) »** (prise en compte de `Boite à idées/20260428_1220_on ce recentre.txt`).

Ce document **ne remplace pas** `docs/plan_de_route.md` (priorités et jalons opérationnels). Il aligne la liste numérotée du fichier `.cursor/rules` avec **ce qui existe** dans le workspace et **ce qui reste backlog**.

**Note** : dans `.cursor/rules`, l’item **5** est absent entre « Pipeline artistique » et « MMO Server » — traité ici comme **5 (vide / à clarifier)** ou fusionné avec 4/6 selon les besoins produit.

| # | Thème (rules) | Emplacements / modules | État (2026-05) |
|---|----------------|---------------------------|----------------|
| **1** | Architecture générale (dossiers, pipelines IA, orchestrateur, agents) | `LBG_IA_MMO/` : `backend/`, `orchestrator/`, `agents/`, `docs/architecture.md` ; client MMO hors dossier monorepo : `web_client/` à la racine workspace | **Réalisé** (incrémental) — évolutions continues |
| **2** | Backend Core (auth, DB, REST, WebSocket, sessions, joueurs) | `backend/` FastAPI ; WebSocket **jeu** : `mmmorpg_server/` ; pas de stack auth/DB multi-tenant « MMO classique » dédiée | **Partiel** : API pilot + proxies ; monde joueur **session WS** (`mmmorpg`) ; **PostgreSQL/Redis/auth JWT** = backlog (`plan_de_route` prio 1/3) |
| **3** | Système IA (orchestrateur, agents, cycle de vie, persistance) | `orchestrator/`, `agents/`, `lbg_agents.dispatch` ; Brain v1 ; persistance **monde** partielle (`mmo_server`, état WS) | **Réalisé** (MVP) ; persistance états agents / bus messages = backlog |
| **4** | Pipeline artistique (2D topdown, tilemaps, automatisation) | `area_gen.py` (zones), assets village / `web_client` ; pas de chaîne SD/Blender industrielle dans ce repo | **Partiel** — voir `plan_mmorpg.md` (pipeline PNJ / visuel = cible long terme) |
| **5** | *(non numéroté dans rules)* | — | **À définir** ou scinder entre 4 et 6 |
| **6** | MMO Server (entités, collisions, chunks, NPC, événements) | `mmmorpg_server/` (WS, collisions, PNJ, pont IA) ; `mmo_server/` (Lyra HTTP, persistance seed) ; `content/world/*.json` | **Réalisé** (MVP LAN) ; **30k NPC / chunks à l’échelle** = backlog `plan_mmorpg.md` |
| **7** | Tests | `pytest` monorepo, `infra/ci/test_pytest.sh`, tests par paquet ; smokes `infra/scripts/smoke_*.sh` | **Réalisé** (ciblé) ; stress / charge = backlog |
| **8** | Documentation | `docs/*`, `bootstrap.md`, README paquets | **Continu** (Priorité 0 `plan_de_route`) |

## Règle de travail

Pour toute session « enchaînement plan global » :

1. Ouvrir **`docs/plan_de_route.md`** → *Prochaine étape concrète* + *Historique*.
2. Utiliser **ce tableau** pour savoir si une case des rules est déjà couverte ou nécessite un **nouveau jalon** explicite.
3. Après livraison : Historique + doc pivot (checklist `.cursor/rules`).
