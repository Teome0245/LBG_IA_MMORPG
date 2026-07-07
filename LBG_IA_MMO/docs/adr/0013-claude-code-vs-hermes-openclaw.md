# ADR 0013 — Poste opérateur VM 140 : Claude Code (Ollama) vs Hermes vs OpenClaw

## Statut

**Accepté** — 2026-07-07

## Contexte

La VM **140** (`lbg-backend`) concentre la **prod** LBG (backend `:8000`, orchestrateur `:8010`, agents `:8020–8055`) et, à terme, un **poste de développement opérateur** accessible en SSH/tmux (PuTTY depuis Windows).

En juillet 2026, nous avons installé **Claude Code** sur 140, configuré pour joindre **Ollama** sur **110** (`gemma4-claude`), en miroir du poste Windows (`scripts/claude-ollama-lan.ps1`, `.claude/settings.json`).

L’application **Ollama Desktop** propose aussi `ollama launch hermes` et `ollama launch openclaw`. Question légitime : aurions-nous dû installer l’un de ces runtimes **à la place** de Claude Code ?

Le monorepo possède déjà une couche « agents » maison :

| Brique LBG | Rôle proche |
|------------|-------------|
| Orchestrateur + `route_intent` | Router d’intentions |
| Agents HTTP (`dialogue`, `quests`, `combat`, `pm`, …) | Spécialistes |
| `pilot_shell` `/pilot/v2/` | UI opérateur type Cursor (chat, outils, modes) |
| Jobs runner (`LBG_JOBS_*`) | Tâches autonomes avec approbation |
| `hybrid_proactive_agent` / Brain | Boucles proactives |
| `companion_bot` | Microservice chat autonome |
| Agent desktop Windows (`C:\Agent_IA`) | Actions poste de travail (ADR 0004) |

## Décision

1. **Sur VM 140, le poste opérateur interactif reste Claude Code** (`claude work .` dans `/opt/LBG_IA_MMO`), lancé via `claude-lbg` → `infra/scripts/claude_ollama_lan.sh`, LLM **Ollama LAN** (`192.168.0.110:11434`, modèle `gemma4-claude`).

2. **Hermes Agent et OpenClaw ne remplacent pas Claude Code** sur 140 pour la phase actuelle (familiarisation + dev non-MMO). Ce sont des runtimes à **périmètre différent** (automation persistante, gateways messagerie, skills auto-générés).

3. **Hermes ou OpenClaw ne sont pas exclus à terme** : évaluation en **couche complémentaire** (VM dédiée ou service séparé), uniquement si un besoin produit n’est pas couvert par l’orchestrateur / `pilot_shell` / jobs — **pas en parallèle sur le même rôle** que Claude Code.

4. **Le modèle Ollama local** (`gemma4-claude`) est un compromis **LAN / coût / confidentialité** ; qualité codage inférieure au cloud Anthropic. Bascule optionnelle vers abonnement Claude documentée mais **non requise** pour l’alignement Windows ↔ 140.

5. **Compte Unix** : poste Claude sur 140 = utilisateur **`lbg`** (alias dans `~lbg/.bashrc`). Pas `sdesharches` (compte MMO / legacy sur d’autres VM).

6. **Vérification d’alignement** : `bash infra/scripts/verify_claude_alignment.sh` (Ollama 110, settings, 140, comparaison env).

## Rôles comparés (référence marché 2026)

| Runtime | Centre de gravité | Fit LBG phase 1 |
|---------|------------------|-----------------|
| **Claude Code** | Session interactive terminal, édition repo, MCP | **Oui** — poste dev 140, parité Windows |
| **Hermes** | Agent toujours allumé, cron, messagerie, skills auto | Partiel — chevauche jobs / proactive / companion |
| **OpenClaw** | Gateway multi-canaux, TaskFlows, gates d’approbation | Partiel — chevauche pilot DevOps, jobs, desktop |

Architecture cible **mature** (hors scope immédiat) :

```text
[ Messagerie / cron ]  Hermes ou OpenClaw (optionnel, VM séparée)
         ↓ délégation
[ Poste dev 140 ]      Claude Code + Ollama 110
         ↓ déploie / configure
[ Prod LAN ]           orchestrateur, agents, pilot_shell, Core3 245/246
```

## Alternatives considérées

| Option | Verdict |
|--------|---------|
| **Hermes seul sur 140** | Rejeté — ne remplace pas l’expérience dev repo ; doublon avec jobs/proactive |
| **OpenClaw seul sur 140** | Rejeté — idem ; risque de confusion avec prod systemd |
| **Abonnement Claude cloud uniquement** | Report — possible plus tard ; actuellement alignement LAN Ollama |
| **Cursor / IDE distant** | Complément WSL existant ; 140 cible Claude Code headless tmux |
| **Étendre uniquement pilot_shell** | Insuffisant pour édition repo riche côté opérateur SSH |

## Conséquences

### Positives

- Parité documentée Windows ↔ 140 (`handoff_windows_vers_vm140.md`, `verify_claude_alignment.sh`).
- Pas de second « cerveau » concurrent sur 140 pendant la phase d’apprentissage.
- Réutilisation de l’investissement Ollama déjà sur **110**.

### Négatives / coûts

- `gemma4-claude` peut être limité pour refactor lourd — accepter ou basculer cloud ponctuellement.
- Hermes/OpenClaw restent à évaluer plus tard (effort d’intégration, chevauchement).
- Deux terminologies (skills ClawHub vs capabilities LBG) si on ajoute OpenClaw/Hermes sans gouvernance.

### Mesures de suivi

- Avant d’installer Hermes/OpenClaw : checklist « besoin non couvert par jobs / pilot / companion ».
- Maintenir `verify_claude_alignment.sh` après tout changement de config Claude.
- Réviser cet ADR si phase 2 MMO ou gateway messagerie opérateur devient prioritaire.

## Références

- `docs/fusion_env_lan.md` — § VM 140 backend + Claude Code
- `docs/handoff_windows_vers_vm140.md`
- `infra/scripts/bootstrap_claude_on_core140.sh`
- `infra/scripts/claude_ollama_lan.sh`
- `infra/scripts/verify_claude_alignment.sh`
- `docs/adr/0004-assistant-local-vs-persona-mmo.md` — périmètres assistant / MMO
- `docs/adr/0011-pilot-shell-react.md` — UI opérateur
