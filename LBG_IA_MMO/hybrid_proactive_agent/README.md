# Agent hybride proactif (`hybrid_proactive_agent`)

Bibliothèque Python **autonome** : elle implémente un agent aux **trois niveaux** décrits dans la vision produit (proactif léger, proactif avancé, agent autonome) via un **moteur d’état interne** (curiosité, tension, objectifs) et une fonction **`decide()`** qui produit des actions typées (question, suggestion, plan, relance autonome).

## Rôle dans le monorepo

Ce paquet est **volontairement découplé** de `orchestrator/` : pas de route FastAPI imposée, pas d’import depuis le routeur tant que tu n’as pas fait le **greffon**. Objectif : faire mûrir le comportement (tests, réglages, option LLM) sans mélanger les responsabilités.

- **Documentation détaillée** : répertoire [`docs/`](docs/) ([index](docs/README.md)).
- **Port navigateur (référence)** : `web_client/src/lib/hybridProactiveEngine.ts` (logique alignée, sans dépendance npm).

## Installation (développement)

```bash
cd LBG_IA_MMO/hybrid_proactive_agent
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
.venv/bin/pytest tests/ -v
```

## Démarrage rapide

```python
from hybrid_proactive_agent import HybridProactiveEngine, integration_hints, LongTermMemoryStore, MemoryEntry

eng = HybridProactiveEngine()
eng.observe_user_turn(
    "Je veux un bot qui prend des initiatives",
    context={"intent": None, "objectif": "assistant", "contraintes": None},
)
action = eng.decide(context={"missing_info": True, "objectif_flou": False})
print(action.mode, action.kind, action.message)

hints = integration_hints(eng.state, {"npc_id": "npc:1", "session_id": "s-abc"})
# hints → mode, tension, curiosité, flags pour un futur routeur / Pilot

mem = LongTermMemoryStore()
mem.append(MemoryEntry(summary="Utilisateur préfère français", tags=["locale"]))
```

### Boucle silence (optionnelle)

Pour simuler l’**autonomie** lorsque l’utilisateur ne parle plus :

```python
import time

# à chaque tick timer (ex. toutes les 5 s) :
eng.tick_silence(5.0)
if eng.state.tension > 0.55:
    nudge = eng.decide({})
```

### Multi-rôles (Architecte / Orchestrateur / Game designer)

```python
from hybrid_proactive_agent import MultiAgentProactiveCoordinator, SpecialistRole

coord = MultiAgentProactiveCoordinator(memory=mem)
coord.set_active_role(SpecialistRole.GAME_DESIGNER)
coord.observe_all("On pourrait ajouter une quête", {"intent": "mmo"})
role_chosen, action = coord.decide_with_memory({"objectif_flou": True})
```

### Enrichissement langagier (LLM)

Passe un générateur de messages au constructeur du moteur :

```python
def gen(template: str, state, ctx: dict) -> str:
    # appeler ton LLM avec template + état sérialisé, retourner le texte final
    return template  # placeholder

eng = HybridProactiveEngine(message_generator=gen)
```

## État d’avancement (« plénement fonctionnel »)

Aujourd’hui le paquet fournit une **couche comportementale déterministe** (heuristiques stables, tests unitaires). Pour un agent « vivant » en production :

1. **Langage** : brancher `message_generator` (ou post-traiter `action.message`).
2. **Politique d’envoi** : cadence, permission utilisateur, canaux (chat, notification) — hors scope de cette lib.
3. **Greffon** : voir [`docs/GREFFON.md`](docs/GREFFON.md).

La faisabilité conceptuelle est développée dans [`docs/FEASIBILITY.md`](docs/FEASIBILITY.md).

## Structure du code

| Module | Contenu |
|--------|---------|
| [`engine.py`](src/hybrid_proactive_agent/engine.py) | Modèles Pydantic, `HybridProactiveEngine`, `integration_hints` |
| [`memory.py`](src/hybrid_proactive_agent/memory.py) | `LongTermMemoryStore`, `MemoryEntry` |
| [`team.py`](src/hybrid_proactive_agent/team.py) | `MultiAgentProactiveCoordinator`, rôles, `team_integration_hints` |

## Tests

```bash
.venv/bin/pytest tests/ -v
```

## Références internes monorepo

- Vue d’ensemble : [`../docs/architecture.md`](../docs/architecture.md) (section *Agent hybride proactif*).
- Suivi : [`../docs/plan_de_route.md`](../docs/plan_de_route.md) (Historique).
