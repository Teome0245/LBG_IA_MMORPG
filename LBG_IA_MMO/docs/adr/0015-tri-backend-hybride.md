# ADR 0015 — Architecture tri-backend hybride (REASON / EXEC / MEDIA)

**Statut** : accepté  
**Date** : 2026-07-12  
**Complète** : ADR 0014, `docs/vision_equipe_fable_autoconsultation.md`

## Contexte

L'écosystème LBG mélange :

- code lourd (Core3 C++, Godot GDScript) ;
- création visuelle (assets GLB, textures) ;
- supervision infra temps réel (Proxmox, VM 140/246, timers) ;
- prise de décision autonome (équipe virtuelle, autoconsult).

Un **agent généraliste unique** (cloud ou local) ne couvre pas ces domaines sans risque sécurité,
coût ou dette opérationnelle. Le poste dev **10** (Cursor / Claude Code) n'est pas disponible H24.

## Décision

Adopter une **architecture tri-backend** sous l'orchestrateur central (VM **140**) :

| Backend | Rôle | Implémentation LBG |
|---------|------|-------------------|
| **REASON** | Raisonnement, code complexe, synthèse PM | `team/reason_llm.py` — Ollama **110**, Groq, Anthropic (API) ; remplace le poste 10 pour L1/L2 équipe |
| **EXEC** | Exécution locale persistante, monitoring, playbooks | `team/openclaw_adapter.py` + skills `infra/openclaw/skills/` — fallback bash si OpenClaw absent |
| **MEDIA** | Génération / pipeline assets visuels | Pygmalion + ComfyUI/Flux (cible) — hors scope immédiat |

### Router–Workers

L'orchestrateur (`orchestrator/team/`) :

1. reçoit objectifs (Pilot, timers, autoconsult) ;
2. découpe en sous-tâches par **persona** (Thémis, Iris, Héphaïstos…) ;
3. route vers le backend adapté ;
4. agrège résultats + followups L1.

### Indépendance poste 10

| Avant | Après (cible) |
|-------|---------------|
| Cursor/Claude sur 10 pour patches GDScript | Iris forge + `reason_llm` sur **140** via Ollama **110** ou API Claude |
| Validation humaine au clavier | Pilot `#/team` L2 token + smokes obligatoires |
| Agent desktop `:5005` optionnel | Conservé pour actions poste propriétaire uniquement |

Le poste 10 devient **optionnel** (dev confort), pas **critique** pour l'équipe 24/7.

### Garde-fous

- **REASON** ne SSH pas Proxmox directement.
- **EXEC** n'écrit pas le Core3 sans playbook validé.
- **Apply forge** : `LBG_IRIS_FORGE_SMOKE_REQUIRED=1` par défaut.
- Write L2 : token Pilot inchangé (ADR 0014).

## Conséquences

- Nouveaux modules : `reason_llm.py`, `openclaw_adapter.py`, `iris_llm_forge.py`.
- Timer autoconsult **12 h** (réduit depuis 24 h).
- Variables `LBG_REASON_*`, `LBG_OPENCLAW_*`, `LBG_IRIS_FORGE_LLM_*`.
- Documentation : `docs/architecture_tri_backend_hybride.md`.

## Alternatives rejetées

- **Tout sur Claude API cloud depuis 140 vers infra** — rejeté : coût + surface d'attaque.
- **OpenClaw seul sans orchestrateur** — rejeté : pas de roster personas ni autoconsult.
- **Ollama seul pour tout** — rejeté : qualité code long horizon insuffisante vs Claude pour REASON.

## Références

- `docs/architecture_tri_backend_hybride.md`
- `docs/jalon_iris_forge_gdscript.md`
- `team/autoconsult_workflow.py`
