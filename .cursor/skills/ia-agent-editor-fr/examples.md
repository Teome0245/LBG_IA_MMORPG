# Exemples d’utilisation — ia-agent-editor-fr

## Exemple 1 — Créer un nouvel agent

**Demande utilisateur**

Crée un agent `orchestrator/agents/blacksmith` capable de : (1) proposer des recettes, (2) estimer des coûts, (3) valider des matériaux. Je veux des schémas JSON et des logs structurés. Ajoute les tests.

**Réponse attendue (structure)**

1) Plan (obligatoire)
- But
- Décisions (capabilities, protocol, constraints)
- Changements fichiers
- Schémas JSON (inputs/outputs/events)
- Logs (champs)
- Tests (unit + intégration)

2) Implémentation
- Dossier agent + code
- Déclaration capabilities/constraints
- Introspection centralisée (mise à jour)
- Registry/router (enregistrement + routage)
- Schémas JSON
- Tests (validation schémas, routage, erreurs)
- README local

## Exemple 2 — Modifier capabilities + constraints

**Demande utilisateur**

Dans l’agent `quest_worker`, ajoute une capability `cancel_quest` et impose une contrainte : ne jamais annuler une quête “main_story” sans validation explicite.

**Réponse attendue (structure)**

1) Plan (obligatoire)
- But
- Décisions (contrainte contrôlable : validation/guard)
- Schémas à modifier (input `cancel_quest`, output)
- Tests à ajouter (main_story -> rejet)

2) Modifications
- Mise à jour déclarative capability + constraint
- Introspection centralisée
- Tests (happy + rejection)
- Logs : outcome `rejected` avec raison non sensible

## Exemple 3 — Ajout schéma JSON et validation

**Demande utilisateur**

Normalise les messages d’entrée/sortie de l’agent `telemetry_agent` avec un schéma JSON strict, et refuse toute clé inconnue.

**Réponse attendue (structure)**

1) Plan (obligatoire)
- Schéma v1 (defs)
- Règles de validation (additionalProperties=false)
- Impact router/registry
- Tests (invalid keys)

2) Implémentation
- Ajout schéma JSON + validation à l’entrée
- Tests unitaires (payload invalide)

