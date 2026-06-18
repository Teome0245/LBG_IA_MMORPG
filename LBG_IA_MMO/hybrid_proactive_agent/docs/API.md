# Contrat d’API (données)

## Entrées

### `observe_user_turn(user_message: str | None, context: dict | None)`

- **`user_message`** : texte brut utilisateur ; alimente la mémoire courte (suffixe borné) et certains signaux lexicaux.
- **`context`** : dictionnaire libre ; les clés reconnues par le moteur sont listées dans `ARCHITECTURE.md`. Toute autre clé est ignorée (extensible).

### `tick_silence(dt_seconds: float)`

À appeler depuis un timer ; **`dt_seconds`** = pas de temps écoulé depuis le dernier appel.

### `decide(context: dict | None)`

Réévalue le mode (via `choose_mode`) puis retourne une **`ProactiveAction`**.

## Sortie : `ProactiveAction`

| Champ | Type | Description |
|-------|------|-------------|
| `kind` | enum | `question`, `suggestion`, `plan`, `wait`, `autonomous_nudge` |
| `message` | str | Texte à afficher ou à envoyer (ou à passer au LLM) |
| `mode` | literal | Mode retenu |
| `question_category` | enum \| None | `clarification`, `exploration`, `hypothese`, etc. |
| `meta` | dict | Métadonnées (ex. liste de sous-objectifs pour un plan) |

## `integration_hints(state, world_context)`

Retour typique :

```json
{
  "hybrid_proactive_mode": "proactif_avance",
  "hybrid_tension": 0.412,
  "hybrid_curiosite": 0.61,
  "suggest_clarify_intent": true,
  "allow_autonomous_followup": false,
  "mmo_npc_id": "npc:lyra",
  "mmo_session_id": "s-123"
}
```

Les clés `mmo_*` ne sont présentes que si fournies dans **`world_context`**.

## Mémoire : `MemoryEntry`

| Champ | Description |
|-------|-------------|
| `ts` | Horodatage (float, défaut : `time.time()`) |
| `summary` | Ligne de résumé pour rappel |
| `tags` | Étiquettes pour scoring lexical |
| `payload` | JSON libre (observations structurées) |

## Sérialisation

Les modèles sont des **`pydantic.BaseModel`** : **`.model_dump()`** / **`.model_dump_json()`** pour logs, traces, persistance d’état.
