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

#### Reconnexion (session)

Le serveur renvoie un `session_token` dans `welcome`. Pour reprendre la même session (même `player_id`) après une déconnexion, renvoyer ce token dans `hello` :

```json
{ "type": "hello", "player_name": "NomDuJoueur", "resume_token": "<session_token>" }
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

`ia_context` (objet optionnel) : seules les clés listées ci‑dessous sont transmises au backend / agent dialogue ; le serveur fixe **`lyra_engagement":"mmo_persona"`** dans le `context` (le client ne peut pas forcer l’assistant poste sur ce pont).

Notes :
- Les PNJ de rôle **`mob`** / **`monster`** ne parlent pas via ce pont : le serveur renvoie un message fixe (combat).

| Clé | Rôle |
|-----|------|
| `session_summary` | Objet **sanitisé** : `tracked_quest`, `last_npc`, `player_note`, `session_mood`, `quest_snapshot`, `memory_hint` (valeurs courtes ; `memory_hint` = liste bornée de **clés** de flags PNJ côté serveur, sans exposer les valeurs). Le **serveur** fusionne un résumé autoritatif (quête joueur + PNJ courant + indice flags) : il **prime** sur `tracked_quest`, `quest_snapshot`, `last_npc` et `memory_hint` ; le client peut compléter avec `player_note` / `session_mood`. Le serveur construit ce merge **même si** `ia_context` est absent ou vide (hors `session_summary` client). |
| `_active_quest_id` | ID quête (string ≤ 80), si non déjà fusionné côté client. |
| `_require_action_json`, `_no_cache` | Booléens (debug / UI). |
| `_world_action_kind` | `"aid"` ou `"quest"` si l’UI impose le type d’`ACTION_JSON`. |
| `history` | Liste optionnelle d’objets `{ "role": "user" \| "assistant", "content": "..." }` : **tours précédents** de la conversation avec ce PNJ (le message **courant** du joueur est envoyé séparément). Sanitisée côté serveur (troncature, plafond de tours). |

**Récompense inventaire via LLM** : lorsque `LBG_DIALOGUE_WORLD_ACTIONS` est actif côté agent, une ligne `ACTION_JSON` avec `kind:"quest"` peut inclure `player_item_id`, `player_item_qty_delta` (entier non nul dans [-50, 50]) et `player_item_label` (optionnel) ; ils sont sanitisés puis transmis dans `output.commit.flags` comme les autres champs quête (même sémantique que `player_item_*` en `world_commit` / HTTP interne).

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
- `world_commit.flags` (objet, optionnel) : ex. `reputation_delta`, `aid_hunger_delta`, **inventaire joueur** (`player_item_id` + `player_item_qty_delta` [+ `player_item_label`]), etc. — même liste blanche que `POST …/dialogue-commit` (HTTP interne). Pour l’inventaire, le joueur est toujours celui de la session WS (pas besoin de champ séparé).

**Effet joueur (session)** : lorsque le commit est appliqué depuis une session WS authentifiée (`hello` puis `move` avec le même joueur), le serveur copie les champs quête reconnus (`quest_id`, `quest_step`, `quest_accepted`, `quest_completed`) dans `entities[].stats.quest_state` pour l’entité joueur — visible dans les snapshots `welcome` / `world_tick`. Les flags **`player_item_*`** mettent à jour **`stats.inventory`** (même joueur). Données **volatiles** (disparaissent à la déconnexion ; pas de persistance disque pour l’instant).

**Client MMO web (`web_client`)** : après réception de `welcome` et à chaque `world_tick`, le client lit l’entité joueur (`kind: "player"`, `id` = `player_id` / id session) et fusionne `stats.quest_state` dans le journal de quêtes local (HUD + `localStorage`), sans remplacer un `npcName` déjà connu si le serveur ne l’expose pas. Les événements `world_event` de type quête enrichissent toujours le journal (ex. nom PNJ).

**Interaction objet (stub, sans LLM)** : en jeu, touche **E** ou bouton **RAMASSER** (panneau PNJ) : envoi d’un `move` avec `world_commit` (`player_item_*`) vers le PNJ **cible** (sélection clavier/souris), si le joueur est assez proche (distance bornée côté client). Même liste blanche de flags que `POST …/dialogue-commit`.

Recette LAN : `infra/scripts/smoke_ws_move_commit_snapshot_lan.sh`.

### `combat` (combat v1 — auto-attack)

Démarre / arrête un combat “auto-attack” côté serveur. Le serveur applique périodiquement des dégâts si la cible est en portée.

Start :

```json
{ "type": "combat", "action": "start", "target_id": "npc:merchant" }
```

Stop :

```json
{ "type": "combat", "action": "stop" }
```

Notes :

- paramètres serveur : `MMMORPG_COMBAT_TICK_S`, `MMMORPG_COMBAT_RANGE_M`, `MMMORPG_COMBAT_BASE_DAMAGE`
- la cible doit être un PNJ vivant (HP > 0)

### `trade` (économie v1 — buy/sell)

Commerce direct avec un PNJ (prix en `item:bronze_coin`). Le serveur applique la transaction **atomiquement** (fonds, quantités, distance) et renvoie un `world_event` `trade` au joueur.

Acheter :

```json
{
  "type": "trade",
  "npc_id": "npc:merchant",
  "side": "buy",
  "item_id": "item:rations",
  "qty": 1,
  "x": 10.0, "y": 0.0, "z": 2.0,
  "trace_id": "trade-unique-001"
}
```

Vendre :

```json
{
  "type": "trade",
  "npc_id": "npc:merchant",
  "side": "sell",
  "item_id": "item:brindille",
  "qty": 1,
  "x": 10.0, "y": 0.0, "z": 2.0,
  "trace_id": "trade-unique-002"
}
```

Règles v1 :

- distance max joueur ↔ PNJ : `MMMORPG_TRADE_MAX_DISTANCE_M`
- les items et prix sont définis côté serveur (shops PNJ)

### `quest` (quêtes gameplay v1)

Accepter une quête (le PNJ donneur dépend du `quest_id`) :

```json
{ "type": "quest", "action": "accept", "quest_id": "quest:brindilles", "npc_id": "npc:merchant", "x": 0, "y": 0, "z": 0 }
```

Rendre une quête (turn-in) :

```json
{ "type": "quest", "action": "turnin", "npc_id": "npc:merchant", "x": 0, "y": 0, "z": 0 }
```

Le serveur met à jour `entities[].stats.quest_state` et envoie des `world_event` `quest_update` / `quest_complete`.

### `job` (métiers v1 — gather/craft)

Récolte (positionnelle v1) :

```json
{ "type": "job", "action": "gather", "kind": "brindille", "resource_id": "res:wood_1", "x": 0, "y": 0, "z": 0 }
```

Craft (stub) :

```json
{ "type": "job", "action": "craft", "recipe_id": "recipe:iron_ingot" }
```

### `door` (intérieurs v1 — entrer/sortir)

Interaction “porte” (extérieur ↔ intérieur).

```json
{ "type": "door", "action": "use", "door_id": "door:auberge_salle_commune", "x": 0, "y": 0, "z": 0 }
```

Notes :
- La porte exige une proximité joueur ↔ porte (garde-fou côté serveur).
- Le serveur bascule `entities[].stats.zone` entre **`village`** et **`interior:<location_id>`**, et filtre `entities`/`locations` sur cette zone.

### HTTP interne — `POST /internal/v1/npc/{npc_id}/dialogue-commit`

Corps JSON :

| Champ | Rôle |
|-------|------|
| `trace_id` | Requis ; idempotence (deuxième envoi avec le même id → accepté sans ré-appliquer). |
| `flags` | Optionnel ; liste blanche (quête, réputation, aid, **inventaire** …). |
| `player_id` | Optionnel ; **obligatoire** dès que `flags` contient `player_item_id` et `player_item_qty_delta` — UUID joueur (équivalent `welcome.player_id`). |

**Inventaire** : `player_item_id` (str ≤ 64) et `player_item_qty_delta` (int, −50…50, non nul) doivent être présents **ensemble** ; `player_item_label` (str ≤ 80) optionnel pour le libellé d’une nouvelle pile. Sans `player_id`, le commit est **refusé** (sans consommer l’idempotence si la validation échoue avant enregistrement du `trace_id`).

Pilot / backend : lors d’un `POST /v1/pilot/route`, le backend transmet `player_id` au commit interne s’il peut le déduire de `context.player_id`, `context.mmmorpg_player_id`, ou d’un `actor_id` de la forme `player:<uuid>`. Pour un **commit inventaire hors LLM**, utiliser aussi `POST /v1/pilot/player-inventory` (corps : `npc_id`, `player_id`, `item_id`, `qty_delta`, `label` optionnel) — voir `pilot_web/README.md`.

## Serveur → client

### `welcome`

```json
{
  "type": "welcome",
  "player_id": "uuid",
  "game_data": { "quests": [], "recipes": [] },
  "session_token": "token",
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

Champs optionnels (combat v1 / gameplay) :

- `world_event` : objet événement (ex. `combat_hit`, `combat_kill`, `dialogue_commit`, etc.)

Exemples :

```json
{
  "type": "combat_hit",
  "source_id": "<player_id>",
  "target_id": "npc:merchant",
  "amount": 5,
  "hp_left": 35,
  "hp_max": 40
}
```

```json
{ "type": "combat_kill", "source_id": "<player_id>", "target_id": "npc:merchant" }
```

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

Champs additionnels selon l’implémentation : `stats` (ex. joueur : HP/MP ; **`stats.inventory`** inventaire session ; **`stats.quest_state`** après commit quête sur la session courante), `world_state` pour les PNJ, `race_id` si renseigné côté serveur, etc.

### HUD client MMO (`web_client`) — fiches personnage

Le client web affiche deux blocs **lecture seule** alimentés par les snapshots `welcome` / `world_tick` :

- **Fiche voyageur** : entité `kind: "player"` dont `id` correspond au joueur courant — nom, rôle, **race** (libellé depuis le catalogue quand disponible, voir ci‑dessous), identifiant (affichage tronqué, id complet en infobulle), **`stats.quest_state`** (quête session serveur), section **Sac (session)** pour **`stats.inventory`** (liste d’objets `{ item_id, qty, label? }`, sac de départ côté serveur — non persisté disque tant qu’il n’y a pas de persistance joueur), et autre contenu de `stats` (hors `quest_state` et hors `inventory`) si présent.
- **Fiche PNJ** : entité `kind: "npc"` correspondant à la cible dialogue (sélection carte ou PNJ le plus proche) — identité, **`world_state`** (réputation, jauges, flags quête PNJ), et **`stats`** éventuels. Rafraîchissement au tick **et** au clic sur un PNJ.

**Bulles de dialogue** (canvas) : titre = nom de la cible ; **sous-titre** = `role` du snapshot lorsqu’il est informatif (pas `civil` ni `player`, underscores → espaces). En attente de réponse IA, la bulle affiche « Réponse en cours… » et un **écho** du message joueur ; la réponse `npc_reply` remplace ce contenu avec un corps de texte plus large qu’auparavant. Le nombre de **lignes affichées** est plafonné côté client pour éviter les répliques hors cadre.

Les chaînes réseau sont échappées à l’affichage. **Libellés de races** : le client tente de charger `race_display` via `GET /v1/pilot/agent-dialogue/world-content` (même origine que la page si servi sous `/mmo/`, sinon `http://<hôte saisi>:8080|8000/…` ou agent direct `:8020/world-content`). L’agent dialogue expose dans la réponse JSON une carte `race_display` : `{ "race:human": "Humain", … }` (voir `GET /world-content` sur l’agent). Le chargement est **asynchrone** après le `welcome` (le jeu n'attend pas le catalogue) ; les fiches se **rafraîchissent** à la réception des libellés. Si aucune source n’est joignable (CORS, service arrêté), l’interface retombe sur l’identifiant `race_id` seul.

### `error`

```json
{ "type": "error", "message": "..." }
```

Notes :

- Anti-spam move : un client qui envoie trop de `move` peut recevoir `message="rate_limited: move"` (en plus du drop silencieux) ; régler côté serveur via `MMMORPG_MOVE_MIN_INTERVAL_S`.
- Inventaire via `world_commit.player_item_*` : le serveur peut exiger une proximité joueur ↔ PNJ (garde-fou gameplay) — `MMMORPG_ITEM_INTERACT_MAX_DISTANCE_M`.
