# Exemples d’utilisation — module-generator-fr

Ces exemples montrent le comportement attendu : **plan d’abord**, puis génération complète (code + tests + docs + ops si applicable).

## Exemple 1 — Module “librairie” (pas de Docker/systemd)

**Demande utilisateur**

Créer un module `mmo_server/world/time` pour gérer le temps du monde (ticks, accélération, pause). Je veux une API simple et des tests.

**Réponse attendue (structure)**

1) Plan (obligatoire)
- But
- Décisions (tick model, source d’horloge, thread-safety)
- Arborescence
- Étapes d’implémentation
- Plan de tests
- Docs

2) Génération
- Arborescence
- Code source (API publique + impl)
- Tests unitaires
- README du module

## Exemple 2 — Service HTTP (Docker oui, systemd optionnel)

**Demande utilisateur**

Ajoute un service FastAPI `backend/api/telemetry` qui expose des métriques et un endpoint de healthcheck.

**Réponse attendue (structure)**

1) Plan (obligatoire)
- But
- Décisions (endpoints, modèles Pydantic, séparation controller/service)
- Arborescence
- Tests (unit + intégration)
- Docs & Ops (Dockerfile recommandé si déploiement)

2) Génération
- Fichiers Python (routes, services, modèles)
- Tests `pytest` (TestClient, cas limites)
- README local (env vars, endpoints)
- Dockerfile si exécutable indépendamment (ou consigne claire si Docker global du repo)

## Exemple 3 — Daemon/worker (systemd oui)

**Demande utilisateur**

Crée un worker `orchestrator/agents/quest_worker` qui tourne en boucle et traite une file de jobs (in-memory pour l’instant). Je veux un service systemd.

**Réponse attendue (structure)**

1) Plan (obligatoire)
- But
- Décisions (boucle, backoff, arrêt propre SIGTERM, logs)
- Arborescence
- Tests (boucle testable sans sleep; injection d’horloge)
- Docs & Ops (systemd requis; Docker optionnel)

2) Génération
- Code (entrypoint, boucle, interfaces)
- Tests unitaires (arrêt propre, backoff, traitement job)
- README (comment lancer localement)
- `infra/systemd/quest_worker.service` (ou chemin cohérent avec le repo)

