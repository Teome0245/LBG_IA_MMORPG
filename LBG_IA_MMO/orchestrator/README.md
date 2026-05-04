# Orchestrator (multi-agents)

Composant responsable de :
- introspection robuste
- classification des intentions (déterministe + **option LLM** pour le langage courant)
- registry des capacités
- routage multi-agents + fallback

## Classification LLM des intentions (optionnel)

Variables (voir `infra/secrets/lbg.env.example`) :

- `LBG_ORCHESTRATOR_INTENT_LLM=1` — active la couche LLM si `LBG_ORCHESTRATOR_INTENT_LLM_BASE_URL` est défini.
- `LBG_ORCHESTRATOR_INTENT_LLM_MODEL`, `LBG_ORCHESTRATOR_INTENT_LLM_API_KEY`, timeouts et `LBG_ORCHESTRATOR_INTENT_LLM_OVERRIDE_CONF`.

Le modèle répond en JSON interne ; seuls des intents « sûrs » sans action structurée sont autorisés (`npc_dialogue`, `quest_request`, `combat_action`, `devops_probe`, `project_pm`, `unknown`). Le routeur ajoute `output.orchestrator_route_meta` (`intent_source`, `assistant_reply` optionnelle).

Surcharge client : `context._intent_classify` = `llm` ou `deterministic` (pilot accueil : **Routage intention**).

## Démarrage

Voir `../../bootstrap.md`.

