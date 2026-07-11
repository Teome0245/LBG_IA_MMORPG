# ADR 0014 — Équipe virtuelle et méta-orchestrateur

**Statut** : accepté  
**Date** : 2026-07-10

## Contexte

L’orchestrateur (VM 140, `:8010`) route des intents vers des agents HTTP en one-shot.
Le moteur de jobs (`services/jobs.py`, Jalon 7) couvre déjà objectifs en langage naturel
avec garde-fous (`action_policy`, tokens, dry-run).

Besoin produit : une **équipe virtuelle** (ops, dev, QA, PM, créatif, monde) qui maintient
l’infra, développe le MMO et, à terme, fait jouer des persos IA — avec autonomie bornée
et approbations humaines.

## Décision

1. **Étendre** l’orchestrateur 140 en **méta-orchestrateur** : rôles persistants + file de
   tâches **SQLite** (`/var/lib/lbg-ia-mmo/team_tasks.db`), distincte des jobs Cowork existants
   (lien optionnel `pilot_job_id`).
2. **Trois couches** :
   - **Studio** (140, poste 10) — dev, QA, PM, infra logicielle ;
   - **Ops** (201 via 140) — sondes, playbooks, write avec approbation ;
   - **Monde** (245) — PNJ, compagnons, joueurs IA — credentials séparés, pas de SSH Proxmox.
3. **Phase A** : rôles `ops`, `qa`, `pm` ; autonomie max **L1** (read-only auto) ;
   write → **L2** + `LBG_TEAM_APPROVAL_TOKEN` (ou token Pilot existant).
4. **UI Pilot** : onglet **Équipe** (`#/team`) — liste tâches, approve, run.
5. **Poste 10** (`192.168.0.10`) : intégration via **agent desktop** `:5005` uniquement ;
   pas de SSH autonome 140→10.
6. **Joueurs IA** (phase D) : comptes dédiés, hors agents studio.

## API (phase A)

- `POST /v1/team/plan`
- `POST /v1/team/tasks`, `GET /v1/team/tasks`, `GET /v1/team/tasks/{id}`
- `POST /v1/team/tasks/{id}/approve`, `.../run`, `.../cancel`

Trace : `agents.team.trace` (JSONL).

## Alternatives rejetées

- **Remplacer jobs Cowork** par team tasks — rejeté : jobs restent pour objectifs NL complexes ;
  team tasks = unité de travail par rôle.
- **Méta-orchestrateur sur 110** — rejeté : 110 = front + LLM ; 140 = cœur agents.
- **Autonomie L3 dès phase A** — rejeté : risque ops trop élevé sans playbooks validés.

## Conséquences

- Nouveau module `orchestrator/team/` + routes dans `router/v1.py`.
- Jobs Pilot et timers existants conservés.
- Phase D documentée dans `architecture_equipe_virtuelle_studio.md`, hors scope A.

## Références

- `docs/architecture_equipe_virtuelle_studio.md`
- `docs/handoff_equipe_virtuelle_2026-07-10.md`
- `docs/assistant_core_plan.md` (Jalon 7 jobs)
- `services/jobs.py`, `services/action_policy.py`
