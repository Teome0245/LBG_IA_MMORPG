## Subagents Cursor (projet LBG_IA_MMO)

Ces subagents sont définis au niveau du workspace dans `.cursor/agents/` (racine du workspace Cursor) et peuvent être invoqués depuis le chat Agent.

### Comment les invoquer

- **Invocation explicite** (recommandé) :

```text
/<nom-du-sous-agent> ...ta demande...
```

- **Invocation “naturelle”** :

```text
Utilise le subagent <nom> pour ...
```

### Sous-agents disponibles

#### `architecte-projet-fr`

- **Rôle**: Architecte du projet (auditeur).
- **Garanties**: cohérence globale, modularité, maintenabilité, testabilité, conformité `.cursor/rules`.
- **Comportement**: **refuse** explicitement toute proposition qui viole les règles et propose une alternative.
- **Mode**: lecture seule.
- **Quand l’utiliser**: avant/après une implémentation non triviale (refactor, ajout de module, nouveaux flux inter-modules).

Exemple :

```text
/architecte-projet-fr passe en revue cette proposition et refuse tout écart aux règles du projet
```

#### `orchestrateuria-fr`

- **Rôle**: responsable de la cohérence des agents IA et du routage.
- **Garanties**: router **déterministe** (tie-breakers stables), fallback explicite, logs structurés.
- **Livrables**: schémas JSON (contrats IO / capabilities / contraintes) + tests `pytest`.
- **Quand l’utiliser**: dès qu’on touche à `orchestrator/` (router, registry, introspection, agents) ou qu’on modifie/ajoute des capacités.

Exemple :

```text
/orchestrateuria-fr génère les schémas JSON des contrats d’agents, assure le déterminisme du router, et ajoute les tests pytest associés
```

#### `orchestrateur-ia-agents-declaratifs-fr`

- **Rôle**: implémentation/refonte d’agents IA déclaratifs côté orchestrateur.
- **Garanties**: agents déclaratifs (capabilities/outils/contraintes/protocole), registry/introspection centralisés, router déterministe + fallback.
- **Livrables**: code + tests + docs dans `orchestrator/` et `orchestrator/agents/<name>/`.
- **Quand l’utiliser**: création/édition d’un agent IA, ou travaux structurants sur `orchestrator/` (registry/router/introspection).

Exemple :

```text
/orchestrateur-ia-agents-declaratifs-fr ajoute un nouvel agent "quest-generator" côté orchestrator avec capabilities/constraints/protocole + tests
```

#### `gamedesigner-mmo-fr`

- **Rôle**: conception des systèmes MMO **data-driven**.
- **Couvre**: NPC, routines civiles, gauges/needs type Lyra, quêtes dynamiques.
- **Garanties**: cohérence du **world state** (invariants, transitions, événements), scénarios reproductibles (seed contrôlée si génération procédurale).
- **Livrables**: schémas de données (JSON/YAML) + validation + tests `pytest` + docs.
- **Quand l’utiliser**: dès qu’on touche à `mmo_server/` (`world/`, `entities/`, `ai/`, `quests/`, `lyra_engine/`, `simulation/`, `classes/`).

Exemple :

```text
/gamedesigner-mmo-fr conçois un système data-driven de routines NPC + gauges Lyra + quêtes dynamiques, et ajoute schémas + tests pour garantir la cohérence du world state
```

