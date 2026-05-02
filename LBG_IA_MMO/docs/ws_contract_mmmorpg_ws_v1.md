# Contrat WebSocket — `mmmorpg_server` (v1)

Ce document décrit le protocole **WebSocket** exposé par `mmmorpg_server` (phase 1), utilisé par :

- un client “joueur” (futur Godot)
- l’UI de test `pilot_web` (panneau “WS test client minimal”)

Objectifs contractuels :

- messages simples JSON (UTF-8)
- **placeholder** puis **réponse finale** remplaçable via le même `trace_id`
- compatibilité forward (champs additionnels autorisés)

---

## 1) Versioning

Tous les messages **serveur → client** incluent :

- `proto: "mmmorpg-ws/1"`

Les clients doivent :

- ignorer les champs inconnus (forward compatible)
- traiter `proto` comme informatif (si absent: accepter, mais logguer)

Les clients devraient :

- ignorer les messages serveur dont `type` est inconnu (logguer + continuer), sauf si tu décides de “fail fast” en dev.

---

## 2) Transport

- **WS** : JSON string (texte) ou bytes UTF-8
- Taille max inbound côté serveur : `config.MAX_WS_INBOUND_BYTES` (frame rejetée avec `type="error"`)

Notes client :

- un `error` serveur n’implique pas forcément une déconnexion : continuer à lire les messages.

---

## 3) Messages client → serveur

### 3.1 `hello`

But : enregistrer le joueur et (optionnellement) déclencher un tour de dialogue PNJ via le pont IA.

Schéma : `docs/schemas/ws/client.hello.schema.json`

Champs notables :

- `world_npc_id` + `text` (optionnels) : si fournis, déclenchent le pont IA
- `ia_context` (optionnel) : **mini contexte borné** (whitelist) transmis à l’IA (ex: `_require_action_json`).
  Les clés inconnues sont ignorées par le serveur WS.

### 3.2 `move`

But : déplacement joueur + (optionnellement) déclencher un tour de dialogue PNJ via le pont IA (sans créer un nouveau type).

Schéma : `docs/schemas/ws/client.move.schema.json`

Notes :

- le serveur applique un anti-spam de move ; l’appel IA est fait **hors** de ce throttle (voir `main.py`)
- si l’agent dialogue renvoie un `commit` monde (`aid`/`quest`), le serveur WS l’applique côté `GameState`
  avec le `trace_id` de la conversation ; l’action est refusée si elle tente de viser un autre PNJ que
  `world_npc_id`.

---

## 4) Messages serveur → client

### 4.1 `welcome`

But : ack du `hello`, et snapshot initial des entités.

Schéma : `docs/schemas/ws/server.welcome.schema.json`

### 4.2 `world_tick`

But : tick monde (20 Hz par défaut), snapshot d’entités, et éventuellement une réplique PNJ.

Schéma : `docs/schemas/ws/server.world_tick.schema.json`

#### Placeholder → final (UX)

Le serveur peut envoyer une réplique “placeholder” (si activé) :

- `npc_reply: "…un instant."` (préfixe stable)
- `trace_id: "<hex>"`

Puis, plus tard, envoyer la réplique finale **avec le même `trace_id`** :

- le client doit **remplacer** l’affichage de la réplique placeholder par la réplique finale en se basant sur `trace_id`.

Règle client recommandée :

- si `npc_reply` est non vide et `trace_id` est non vide :
  - si `npc_reply` commence par `…un instant.` ⇒ afficher en “pending”
  - sinon ⇒ remplacer la thread `trace_id` par la version finale

#### Timeouts / erreurs (comportement recommandé client)

- si un placeholder est affiché et qu’aucune réponse finale n’arrive dans un délai “UX” (ex. 30–120 s),
  le client devrait proposer une action (bouton “réessayer”, “annuler”, etc.) plutôt que de rester bloqué.
- si le serveur envoie une fin explicite (ex. `"Désolé, je ne peux pas t'aider maintenant."`) avec le même `trace_id`,
  cela doit aussi **remplacer** le placeholder.

### 4.3 `error`

But : erreur protocolaire (JSON invalide, type inconnu, message trop gros, etc.).

Schéma : `docs/schemas/ws/server.error.schema.json`

---

## 5) Entités (`entities[]`)

Forme (commune `welcome`/`world_tick`) :

- `id` (string)
- `kind` (`"player"` | `"npc"`)
- `name` (string)
- `x,y,z` (number)
- `vx,vy,vz` (number)

Schéma : `docs/schemas/ws/entity.snapshot.schema.json`

---

## 6) Idempotence / corrélation côté monde (HTTP interne)

Le `trace_id` issu du pont IA sert aussi à :

- corréler `GET /internal/v1/npc/{npc_id}/lyra-snapshot?trace_id=...`
- idempotence sur `POST /internal/v1/npc/{npc_id}/dialogue-commit` (même `trace_id` ⇒ noop accepté)
- idempotence des commits `aid`/`quest` renvoyés par l’agent dialogue puis appliqués directement par le pont WS

Notes d’implémentation (HTTP interne `mmmorpg_server`) :

- `npc_id` est dans un segment d’URL : un client navigateur va typiquement l’URL-encoder (`npc:merchant` → `npc%3Amerchant`).
  L’endpoint accepte donc les valeurs encodées.
- pour un usage navigateur (pilot_web), l’HTTP interne inclut des headers **CORS** et répond aux `OPTIONS` preflight.

Cf. `docs/fusion_pont_jeu_ia.md`.

