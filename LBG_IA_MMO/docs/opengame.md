# OpenGame — forge de prototypes orchestrée

## Objectif

OpenGame est intégré comme **forge de prototypes** pilotée par l'orchestrateur, conformément à `docs/adr/0003-opengame-forge-prototypes.md`.

Le flux cible est :

```text
backend/pilot -> orchestrator -> prototype_game -> agent.opengame -> sandbox OpenGame
```

OpenGame ne devient pas un second orchestrateur du produit. Il génère des prototypes isolés ; toute promotion vers le MMO reste manuelle, revue, testée et documentée.

## État actuel

Fonctionnel côté projet :

- capability `prototype_game` dans l'orchestrateur ;
- routage vers `agent.opengame` via `context.opengame_action` ;
- dry-run par défaut ;
- exécution réelle possible uniquement avec double verrou ;
- sandbox obligatoire ;
- refus si le dossier cible existe déjà avec du contenu ;
- lancement sans `--yolo` ;
- timeout et capture bornée de stdout/stderr ;
- audit `agents.opengame.audit`.

Non inclus automatiquement :

- installation de la CLI `opengame` ;
- clés API OpenGame/providers ;
- preview web/Nginx des prototypes ;
- promotion automatique dans `web_client/`, `pilot_web/` ou le coeur MMO.

## Prérequis

Sur la machine qui exécute `agent.opengame` :

- Node.js 20+ ;
- npm ;
- CLI `opengame` disponible dans le `PATH` ou via `LBG_OPENGAME_BIN` ;
- variables OpenGame/providers nécessaires selon le mode utilisé (`OPENAI_API_KEY`, `OPENAI_BASE_URL`, `OPENAI_MODEL`, `OPENGAME_*`, etc.).

Vérification rapide :

```bash
node -v
npm -v
command -v opengame
```

## Installation OpenGame

Recommandation : installer OpenGame **hors du monorepo**, par exemple dans `~/tools/OpenGame` ou `/opt/opengame-src`. Ne pas vendor le dépôt OpenGame directement dans `LBG_IA_MMO/` sans décision dédiée.

Exemple dev local :

```bash
mkdir -p ~/tools
cd ~/tools
git clone https://github.com/leigest519/OpenGame.git
cd OpenGame
npm install
npm run build
npm link
command -v opengame
```

Si `npm link` n'est pas souhaité, renseigner le binaire explicitement :

```bash
export LBG_OPENGAME_BIN="/chemin/vers/opengame"
```

## Configuration LBG

Variables côté `infra/secrets/lbg.env` :

```bash
# Racine sandbox : les prototypes sont générés sous ce dossier.
LBG_OPENGAME_SANDBOX_DIR="/var/lib/lbg/opengame"

# Sécurité : dry-run par défaut.
LBG_OPENGAME_DRY_RUN="1"
LBG_OPENGAME_EXECUTION_ENABLED="0"

# CLI et bornes.
LBG_OPENGAME_BIN="opengame"
LBG_OPENGAME_TIMEOUT_S="900"
LBG_OPENGAME_MAX_OUTPUT_CHARS="12000"

# Optionnel : impose une approbation par appel.
LBG_OPENGAME_APPROVAL_TOKEN="change-moi"

# Audit.
LBG_OPENGAME_AUDIT_LOG_PATH="/var/log/lbg/opengame_audit.jsonl"
LBG_OPENGAME_AUDIT_STDOUT="1"
```

Variables OpenGame/providers, à adapter selon le fournisseur utilisé :

```bash
OPENAI_API_KEY="..."
OPENAI_BASE_URL="https://api.openai.com/v1"
OPENAI_MODEL="gpt-4o"

# Exemples optionnels selon les providers OpenGame.
OPENGAME_IMAGE_PROVIDER="openai-compat"
OPENGAME_IMAGE_API_KEY="..."
```

Ne jamais committer les vraies clés. `infra/secrets/lbg.env.example` ne contient que des placeholders.

## Appel dry-run

Le dry-run valide le routage, la sandbox et le plan d'exécution sans lancer OpenGame.

Via l'orchestrateur :

```bash
curl -sS http://127.0.0.1:8010/v1/route \
  -H 'Content-Type: application/json' \
  -d '{
    "actor_id": "svc:opengame",
    "text": "Prototype Snake sombre",
    "context": {
      "_trace_id": "manual-opengame-dryrun-1",
      "opengame_action": {
        "kind": "generate_prototype",
        "project_name": "snake_dark",
        "prompt": "Build a Snake clone with WASD controls and a dark theme."
      }
    }
  }'
```

Résultat attendu :

- `intent: "prototype_game"` ;
- `routed_to: "agent.opengame"` ;
- `output.outcome: "dry_run"` ;
- `output.planned.command` avec `opengame -p <prompt> --approval-mode auto-edit`.

## Exécution réelle

À activer uniquement dans une sandbox contrôlée :

```bash
export LBG_OPENGAME_DRY_RUN="0"
export LBG_OPENGAME_EXECUTION_ENABLED="1"
export LBG_OPENGAME_SANDBOX_DIR="$PWD/generated_games/opengame"
```

Si `LBG_OPENGAME_APPROVAL_TOKEN` est défini, fournir `context.opengame_approval`.

Exemple :

```bash
curl -sS http://127.0.0.1:8010/v1/route \
  -H 'Content-Type: application/json' \
  -d '{
    "actor_id": "svc:opengame",
    "text": "Prototype Snake sombre",
    "context": {
      "_trace_id": "manual-opengame-run-1",
      "opengame_approval": "change-moi",
      "opengame_action": {
        "kind": "generate_prototype",
        "project_name": "snake_dark",
        "prompt": "Build a Snake clone with WASD controls and a dark theme."
      }
    }
  }'
```

L'agent :

- crée la sandbox si nécessaire ;
- refuse un dossier cible non vide ;
- résout `opengame` via `PATH` ou `LBG_OPENGAME_BIN` ;
- lance la commande sans shell libre ;
- n'utilise pas `--yolo` ;
- renvoie `stdout_preview`, `stderr_preview`, `returncode`.

## Résultats et preview

Les prototypes sont générés sous :

```text
${LBG_OPENGAME_SANDBOX_DIR}/${project_name}
```

OpenGame peut produire un projet Vite ou un autre format web selon son template. Pour tester manuellement :

```bash
cd "$LBG_OPENGAME_SANDBOX_DIR/snake_dark"
npm install
npm run dev
```

La preview via `/pilot/` ou Nginx n'est pas encore branchée. Tant que ce n'est pas fait, la consultation reste manuelle depuis le dossier sandbox.

## Garde-fous

Règles importantes :

- pas de `--yolo` côté `agent.opengame` ;
- pas de génération dans le coeur du repo ;
- pas d'écrasement d'un prototype existant ;
- pas d'exécution réelle sans `LBG_OPENGAME_DRY_RUN=0` et `LBG_OPENGAME_EXECUTION_ENABLED=1` ;
- promotion vers le MMO uniquement par changement de code normal : revue, tests, docs, déploiement ;
- ne pas importer de contenus sous IP tierce depuis les démos OpenGame.

## Tests

Tests ciblés :

```bash
cd LBG_IA_MMO
. .venv-ci/bin/activate
pytest -q \
  agents/tests/test_opengame_executor.py \
  orchestrator/tests/test_route.py \
  orchestrator/tests/test_capabilities.py \
  orchestrator/tests/test_classifier.py
```

Dernière validation locale :

```text
20 passed, 2 warnings
```

Les warnings connus concernent `FastAPI on_event` et ne sont pas liés à OpenGame.

## Prochaines étapes

- Installer et tester la CLI OpenGame sur la machine cible.
- Ajouter un smoke LAN dédié une fois la CLI disponible.
- Ajouter une vue `/pilot/` pour lister les prototypes générés.
- Ajouter éventuellement un nettoyage/archivage des prototypes anciens.
- Documenter la procédure de promotion d'un prototype vers une feature MMO.
