# Phase H — Perception sociale des joueurs IA

Objectif : faire passer Lia, Nix et les futurs joueurs IA de simples personnages qui parlent à des agents incarnés qui perçoivent les messages récents et y répondent.

## Flux MVP

1. Le sidecar/orchestrateur génère une action Core3 (`say`, `interact`, etc.) ou un joueur humain parle dans le spatial.
2. Le screenplay Lua ou le hook natif `ChatManagerImplementation` écrit un événement dans `ia_bridge/events.jsonl`.
3. Le sidecar expose ces événements via `GET /v1/events`.
4. La boucle `core3_player_autonomy.py` lit les événements ciblant son joueur.
5. Si un événement récent lui est adressé, l'IA répond en priorité avant de reprendre son comportement métier.

## Contrat événement

Chaque ligne de `ia_bridge/events.jsonl` est un JSON :

```json
{
  "version": 1,
  "event_id": "1779798766-1",
  "ts": 1779798766,
  "type": "core3.ai_say",
  "actor": "Nix",
  "target": "Lia",
  "message": "Lia, quelle action veux-tu que je coordonne maintenant ?",
  "zone": "tatooine",
  "x": 3468.57,
  "y": -4787.24,
  "z": 5.0,
  "source_line": "..."
}
```

Types MVP :

- `core3.ai_say` : parole spatiale produite par un joueur IA.
- `core3.ai_interact` : interaction ciblée produite par un joueur IA.
- `core3.player_spatial_chat` : parole spatiale produite par un joueur humain et adressée à `Lia` ou `Nix`.

## Hook chat humain

Le serveur Core3 capte maintenant les messages spatiaux dans `ChatManagerImplementation::handleSpatialChatInternalMessage`.

Filtrage MVP :

- ignore les messages émis par `Lia` et `Nix` pour éviter les boucles.
- écrit un événement seulement si le texte contient `lia` ou `nix`.
- conserve l'acteur, la cible déduite, le message, la zone et la position du joueur.

Exemple en jeu :

```text
Lia, danse si tu m'entends
Nix, viens voir cette zone
```

## API sidecar

```bash
curl -s 'http://127.0.0.1:8791/v1/events?player=Lia&limit=20'
```

Paramètres :

- `player` : cible à filtrer (`Lia`, `Nix`, etc.).
- `after` : ne retourne que les événements après cet `event_id`.
- `limit` : 1 à 200.
- `include_actor=1` : inclut aussi les événements émis par ce joueur.

## Mémoire courte

Chaque boucle joueur garde son dernier événement traité dans :

```text
/tmp/lbg-core3-player-autonomy/<player_id>.last_event
```

Configurable via `LBG_CORE3_PLAYER_AUTONOMY_STATE_DIR`.

## Limites

Le hook humain est volontairement strict : il ne transforme pas tout le chat spatial en perception IA. Pour l'instant, seuls les messages qui nomment explicitement `Lia` ou `Nix` deviennent des événements `core3.player_spatial_chat`.
