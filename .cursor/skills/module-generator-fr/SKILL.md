---
name: module-generator-fr
description: Génère un module complet (structure de dossiers, code source, tests unitaires, documentation, Dockerfile si nécessaire, service systemd si daemon). Toujours proposer un plan avant génération. À utiliser quand l’utilisateur demande de créer/ajouter un module, une brique, un composant majeur, un service, ou un sous-système.
---

# Générateur de module (FR)

## Règle d’or

Toujours commencer par un **plan** (court, actionnable) avant de générer des fichiers ou du code.

## Objectif

Quand l’utilisateur demande un nouveau module, produire un livrable **complet et cohérent** comprenant :

- structure de dossiers
- code source
- tests unitaires (et tests d’intégration si pertinent)
- documentation (README local + docstrings des APIs publiques)
- Dockerfile **si** le module est exécutable/déployable
- service systemd **si** le module tourne en daemon (process long-lived)

## Entrées minimales à déduire / collecter

Si l’utilisateur ne précise pas tout, déduire raisonnablement à partir du contexte du repo. Sinon, poser des questions **courtes** (max 5) uniquement sur :

- nom du module et sa responsabilité (1 phrase)
- type : librairie / CLI / service HTTP / daemon worker / simulation loop
- API attendue (fonctions publiques, endpoints, messages/events)
- dépendances internes (où se branche le module)
- contraintes d’exécution (CPU/GPU, I/O, temps réel, multi-process, etc.)

## Workflow imposé

### 1) Plan (obligatoire)

Produire un plan en Markdown avec :

- **But** (1 phrase)
- **Décisions** (2–5 puces) : type de module, frontières, interfaces, persistance, erreurs/logs
- **Arborescence** (prévue)
- **Implémentation** (étapes courtes)
- **Tests** (ce qui est couvert)
- **Docs & Ops** (README, Docker/systemd si applicable)

Ne pas commencer la génération tant que le plan n’est pas affiché.

### 2) Génération

Générer ensuite, dans cet ordre :

1. **Arborescence** (liste de dossiers/fichiers)
2. **Code** (APIs publiques d’abord, puis détails internes)
3. **Tests** (pytest/unittest/équivalent selon stack, avec fixtures minimales)
4. **Docs** (`README.md` du module + docstrings)
5. **Ops** (Dockerfile, systemd, scripts) uniquement si applicable

### 3) Boucle de validation

Après génération :

- vérifier cohérence imports/paths
- s’assurer que les tests ciblent les comportements (pas seulement la couverture)
- proposer 1–3 améliorations optionnelles (observabilité, perf, DX)

## Conventions de sortie

- **Chemins** : toujours style Linux (`/`, pas de chemins Windows).
- **Modularité** : module autonome, interfaces explicites, dépendances minimales.
- **Contrôleurs** : pas de logique métier dans les contrôleurs (si API) : services + modules.
- **Typage** : favoriser code typé (Python: annotations, Pydantic si API, etc.).
- **Erreurs** : erreurs explicites, messages utiles, pas d’exceptions silencieuses.
- **Logs** : logs structurés pour les daemons/services, niveau configurable.

## Décisions conditionnelles (Docker / systemd)

### Dockerfile (si nécessaire)

Créer un `Dockerfile` **uniquement si** :

- le module est un service déployable (HTTP, worker, simulation server), ou
- l’utilisateur le demande explicitement, ou
- le module a des dépendances système non triviales et gagne à être containerisé.

Le Dockerfile doit être minimaliste, reproductible, et adapté au runtime (ex. Python slim).

### systemd (si daemon)

Créer un fichier `*.service` **uniquement si** le module :

- tourne en continu (daemon / worker / simulation loop),
- et s’exécute sur Linux hôte (pas seulement en container).

Le service doit inclure :

- `ExecStart` clair
- `Restart=on-failure`
- `User`/`Group` (ou consigne explicite si inconnu)
- `WorkingDirectory`
- variables d’environnement via `EnvironmentFile=` si nécessaire

## Templates (à suivre)

### Template README module

Inclure au minimum :

- **But**
- **API** (fonctions / classes / endpoints)
- **Exemples d’usage**
- **Tests** (commande)
- **Configuration** (env vars, fichiers)
- **Exécution** (si service/daemon)

### Template tests

Les tests doivent :

- valider les chemins heureux + 2–3 cas limites
- tester la sérialisation/validation (si modèles)
- éviter les sleeps/flaky tests

## Fichiers annexes

- Pour des exemples complets de demandes/réponses attendues : voir `examples.md`.

