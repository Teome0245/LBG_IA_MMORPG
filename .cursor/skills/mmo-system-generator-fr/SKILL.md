---
name: mmo-system-generator-fr
description: Génère un système MMO data-driven (combat, économie, météo, quêtes, etc.) incluant entités, events, interactions, tests et documentation. Toujours proposer un plan avant génération. À utiliser quand l’utilisateur demande d’ajouter un nouveau système gameplay/simulation ou d’étendre un système existant.
---

# Générateur de système MMO data-driven (FR)

## Règle d’or

Toujours commencer par un **plan** (court, actionnable) avant de générer des fichiers ou du code.

## Objectif

Produire un système MMO **data-driven** et **modulaire** qui comprend :

- **système** (combat, économie, météo, quêtes, factions, métiers, etc.)
- **entités** (composants, états, ressources)
- **events** (événements internes + externes, bus, handlers)
- **interactions** (règles, déclencheurs, effets, conditions)
- **tests** (unitaires + scénarios simulation si pertinent)
- **documentation** (README + docstrings des APIs publiques)

## Principes non négociables

- Data-driven : les règles/paramètres sont dans des données (JSON/YAML/CSV), le code est un moteur générique.
- Modulaire : interfaces explicites, dépendances minimales, intégration propre.
- Testable : logique pure isolée, injection de temps/PRNG, pas de sleeps.
- Maintenable : nomenclature cohérente, séparation `domain`/`engine`/`adapters`.

## Entrées minimales à déduire / collecter

Si l’utilisateur n’a pas donné ces éléments, poser au plus 5 questions courtes :

- quel **système** (ex: “météo”) + périmètre (MVP)
- quelles **entités** et états manipulés
- quels **events** (liste 5–15) + qui les émet/consomme
- quelles **interactions** (règles clé, priorités, conflits)
- contraintes (temps réel, déterminisme, perf, persistance)

## Workflow imposé

### 1) Plan (obligatoire)

Afficher un plan en Markdown contenant :

- **But**
- **Périmètre MVP** (ce qui est dedans / dehors)
- **Modèle de données** (entités + ressources + tables/config)
- **Catalogue d’events** (nom, payload, producteurs/consommateurs)
- **Interactions** (règles, ordre d’évaluation, résolution de conflits)
- **Arborescence** (dossiers/fichiers)
- **Implémentation** (étapes courtes)
- **Tests** (unit + scénarios)
- **Docs** (README + exemples de config)

Ne pas commencer la génération tant que le plan n’est pas affiché.

### 2) Génération (ordre recommandé)

1. **Arborescence**
2. **Schémas/contrats de données** (configs, payloads d’events)
3. **Moteur du système** (logique pure, déterministe)
4. **Adapters** (intégration au world/simulation loop si existant)
5. **Tests** (comportements + cas limites + propriété déterministe)
6. **Documentation** (README + exemples de configs)

### 3) Boucle de validation

Après génération :

- vérifier que les configs pilotent réellement le comportement (pas de constantes “cachées”)
- vérifier que le système est déterministe avec seed PRNG fixe (si PRNG)
- vérifier que les events ont un contrat stable (schéma + tests)

## Patterns recommandés (data-driven)

### Configs

- définir un dossier `data/` (ou équivalent) contenant :
  - paramètres globaux
  - tables de règles
  - définitions d’items/skills/effets
- prévoir un validateur de config (schéma JSON ou validation Pydantic)

### Events

- events nommés de façon stable (`system.event_name`)
- payload minimal, versionnable si nécessaire
- handlers purs quand possible (input state + event -> output state + emitted events)

### Interactions

- interactions exprimées comme règles (conditions -> effets)
- résolution de conflits définie (priorité, dernier gagnant, accumulation, etc.)

## Conventions de sortie

- Chemins style Linux (`/`).
- Code typé (Python: annotations).
- Pas de logique “monolithe” : séparer `engine/`, `domain/`, `data/`, `tests/`.

## Fichiers annexes

- Exemples de demandes/réponses attendues : `examples.md`

