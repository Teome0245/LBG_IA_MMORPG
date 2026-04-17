---
name: ia-agent-editor-fr
description: Crée ou modifie un agent IA en respectant un format déclaratif (capabilities, constraints, protocol), l’introspection centralisée, des schémas JSON, des tests, et des logs structurés. À utiliser quand l’utilisateur demande d’ajouter/mettre à jour un agent, une capability, un outil, un protocole, ou l’intégration au router/registry.
---

# Éditeur d’agent IA (FR)

## Règle d’or

Toujours proposer un **plan** avant toute génération ou modification substantielle.

## Objectif

Créer ou modifier un agent IA (dossier, code, schémas, tests, docs) en garantissant :

- **capabilities** déclaratives (ce que l’agent sait faire)
- **constraints** explicites (limites, risques, garde-fous)
- **introspection centralisée** (pas dispersée dans chaque agent)
- **schémas JSON** (contrats stables pour messages/config/capabilities)
- **tests** (unitaires + intégration si routeur/registry)
- **logs structurés** (champs, niveaux, corrélation)

## Entrées minimales à déduire / collecter

Si manquant, poser au plus 5 questions courtes :

- nom de l’agent (`snake_case` ou `kebab-case`) + but (1 phrase)
- liste initiale des capabilities (3–10 items)
- protocole d’I/O (input/output JSON, événements, outils)
- contraintes clés (sécurité, coût, latence, données sensibles)
- points d’intégration (registry/router/introspection)

## Workflow imposé

### 1) Plan (obligatoire)

Afficher un plan en Markdown contenant :

- **But**
- **Décisions** (capabilities, protocol, constraints, schémas)
- **Changements fichiers** (liste)
- **Schémas JSON** (quoi, où, versioning)
- **Logs** (champs minimaux)
- **Tests** (unitaires + intégration)

Ne pas générer/modifier avant d’avoir affiché ce plan.

### 2) Implémentation (ordre recommandé)

1. **Déclaration** : créer/mettre à jour la définition déclarative de l’agent
2. **Introspection** : brancher les métadonnées agent dans le module central d’introspection
3. **Registry/Router** : enregistrer l’agent/capabilities et routage déterministe + fallback
4. **Schémas JSON** : ajouter/mettre à jour les contrats (request/response/events/config)
5. **Logs structurés** : instrumentation (correlation id, agent, capability, outcome, latence)
6. **Tests** : tests ciblant le comportement (routage, validation schémas, erreurs)
7. **Docs** : README local (capabilities, protocole, config, exécution)

### 3) Boucle de validation

Après modifications :

- vérifier que l’introspection reste **unique et centralisée**
- vérifier que toutes les entrées/sorties agent sont validées contre des schémas
- vérifier que les tests couvrent au moins : routage, cas limites, erreurs, logs

## Conventions de conception

### Capabilities

- capabilities = **noms stables** + description courte + schéma d’input/output
- chaque capability doit déclarer : **préconditions**, **effets**, **erreurs possibles**

### Constraints

- constraints doivent être **exécutables/contrôlables** (validation, filtres, refus explicites)
- inclure des garde-fous : données sensibles, prompt injection, actions irréversibles

### Introspection centralisée

- maintenir **un seul module** source de vérité (inventaire agents/capabilities/constraints)
- éviter l’introspection “au fil de l’eau” dans chaque agent

### Schémas JSON

- schémas versionnés si le contrat évolue
- validation systématique à l’entrée (et à la sortie si critique)
- schémas réutilisables (defs/components) plutôt que duplication

### Logs structurés

Les logs doivent inclure (minimum) :

- `timestamp`, `level`
- `agent`, `capability`
- `request_id` (ou correlation id)
- `outcome` (`success|error|rejected`)
- `latency_ms`
- champs d’erreur : `error_type`, `error_message` (sans fuite de secrets)

## Points d’attention (anti-patterns)

- ne pas “câbler” une capability sans la déclarer (capability fantôme)
- ne pas modifier le routage sans tests d’intégration
- ne pas ajouter un schéma sans tests de validation (happy + invalid)
- ne pas logger de secrets (tokens, prompts sensibles, PII)

## Fichiers annexes

- Exemples de demandes/réponses attendues : `examples.md`

