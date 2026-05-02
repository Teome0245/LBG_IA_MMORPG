# Protocole réseau — Phase 1

Transport : **WebSocket** (`ws://host:port`).

Encodage : **JSON** une ligne par message (UTF-8).

**Côté serveur (Phase 1)** : taille max d’une frame configurable (`MMMORPG_MAX_WS_INBOUND_BYTES`, défaut 64 KiB) ; les commandes `move` trop rapprochées peuvent être ignorées (`MMMORPG_MOVE_MIN_INTERVAL_S`).

## Client → serveur

### `hello`

Authentification minimale (Phase 1 : `player_name` seulement).

```json
{ "type": "hello", "player_name": "NomDuJoueur" }
```

#### Option (pont jeu → IA, sans nouveau `type`)

Si `MMMORPG_IA_BACKEND_URL` est défini côté serveur, `hello` peut inclure des champs optionnels
pour demander une première réplique PNJ au moment de la connexion (appel interne au backend :
`POST /v1/pilot/internal/route` par défaut, configurable via `MMMORPG_IA_BACKEND_PATH`).

Headers optionnels sur l’appel backend :
- `X-LBG-Service-Token` (valeur `MMMORPG_IA_BACKEND_TOKEN`) si un token service est requis côté backend
- `X-LBG-Trace-Id` (généré) pour corrélation dans les logs backend/orchestrateur/agents

```json
{
  "type": "hello",
  "player_name": "NomDuJoueur",
  "world_npc_id": "npc:innkeeper",
  "npc_name": "Mara l’aubergiste",
  "text": "Une chambre pour la nuit, s'il vous plaît."
}
```

### `move`

Mise à jour intention de position (le serveur valide / applique).

```json
{ "type": "move", "x": 10.5, "y": 0.0, "z": -3.2 }
```

#### Option (pont jeu → IA, sans nouveau `type`)

Si `MMMORPG_IA_BACKEND_URL` est défini côté serveur, `move` peut inclure des champs optionnels
pour déclencher une réplique PNJ **après** `hello` (même mécanisme que `hello` : placeholder + réponse finale sur `world_tick`).

```json
{
  "type": "move",
  "x": 10.5,
  "y": 0.0,
  "z": -3.2,
  "world_npc_id": "npc:innkeeper",
  "npc_name": "Mara l’aubergiste",
  "text": "Et pour le souper ?"
}
```

### `move` — option `world_commit` (gameplay v1, **sans** pont IA)

Permet d’appliquer un **commit PNJ** synchronisé sur le même message que le déplacement, **sans** appeler le backend LLM. Même liste blanche de `flags` que `POST …/dialogue-commit` (HTTP interne).

**Incompatibilité** : si le `move` déclenche aussi le pont IA (`text` non vide **et** `world_npc_id` non vide), la présence de `world_commit` est **refusée** (erreur `type: error`).

Exemple (réputation locale uniquement) :

```json
{
  "type": "move",
  "x": 3.0,
  "y": 0.0,
  "z": 2.0,
  "world_commit": {
    "npc_id": "npc:merchant",
    "trace_id": "client-unique-trace-001",
    "flags": { "reputation_delta": 7 }
  }
}
```

Champs :

- `world_commit.npc_id` (string, requis) : PNJ cible (`npc:…`).
- `world_commit.trace_id` (string, requis) : idempotence (même sémantique que le commit HTTP).
- `world_commit.flags` (objet, optionnel) : ex. `reputation_delta`, `aid_hunger_delta`, etc. (voir serveur / tests).

**Effet joueur (session)** : lorsque le commit est appliqué depuis une session WS authentifiée (`hello` puis `move` avec le même joueur), le serveur copie les champs quête reconnus (`quest_id`, `quest_step`, `quest_accepted`, `quest_completed`) dans `entities[].stats.quest_state` pour l’entité joueur — visible dans les snapshots `welcome` / `world_tick`. Donnée **volatile** (disparaît à la déconnexion ; pas de persistance disque pour l’instant).

Recette LAN : `infra/scripts/smoke_ws_move_commit_snapshot_lan.sh`.

## Serveur → client

### `welcome`

```json
{
  "type": "welcome",
  "player_id": "uuid",
  "planet_id": "terre1",
  "world_time_s": 123.45,
  "day_fraction": 0.25,
  "entities": [ ... ]
}
```

Champs optionnels (si pont jeu → IA activé et la requête `hello` contient `world_npc_id` + `text`) :

- `npc_reply` : réplique texte PNJ
- `trace_id` : identifiant de trace (corrélation backend/orchestrateur/agents)

Note : pour éviter de bloquer `welcome`, l’implémentation peut renvoyer `npc_reply`/`trace_id`
soit dans `welcome`, soit sur le prochain `world_tick` (champs optionnels).
Pour fiabiliser (même si l’IA est lente), une implémentation peut aussi renvoyer d’abord une
**réplique placeholder** puis une réplique “finale” plus tard.

Règle (implémentation actuelle `mmmorpg_server`) :

- le placeholder et la réponse finale partagent le **même `trace_id`**
- le client doit **remplacer** l’affichage du placeholder par la réponse finale en se basant sur `trace_id`

### `world_tick`

Diffusion périodique (état monde).

```json
{
  "type": "world_tick",
  "world_time_s": 200.0,
  "day_fraction": 0.33,
  "entities": [ ... ]
}
```

Champs optionnels (pont jeu → IA) :

- `npc_reply` : réplique PNJ (placeholder ou final)
- `trace_id` : identifiant de corrélation stable placeholder → final

### `entity_snapshot`

Une entité : joueur ou PNJ.

```json
{
  "id": "uuid",
  "kind": "player",
  "name": "Nom",
  "x": 0, "y": 0, "z": 0,
  "vx": 0, "vy": 0, "vz": 0
}
```

`kind` : `"player"` | `"npc"`.

Champs additionnels selon l’implémentation : `stats` (ex. joueur : HP/MP ; **`stats.quest_state`** après commit quête sur la session courante), `world_state` pour les PNJ, etc.

### `error`

```json
{ "type": "error", "message": "..." }
```
