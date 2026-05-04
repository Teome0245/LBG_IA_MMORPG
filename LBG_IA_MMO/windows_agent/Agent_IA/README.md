# Agent Windows (Agent_IA)

Ce module contient le **worker Windows** (HTTP) exécuté sur le poste utilisateur.

## Chemin cible sur le PC Windows

Déploiement attendu : `C:\Agent_IA\`

## Démarrage

1) Copier le module sur Windows dans `C:\Agent_IA\`
2) Créer `C:\Agent_IA\desktop.env` (voir `desktop.env.example`)
3) Lancer :

```powershell
C:\Agent_IA\run_agent.cmd
```

## Endpoints

- `GET /healthz`
- `POST /invoke` (utilisé par `LBG_AGENT_DESKTOP_URL`)
- `GET /capabilities`, `POST /execute`, `POST /install` (historique / expérimental — pas requis pour `desktop_control`)

## Config hot-reload

Le fichier `desktop.env` est relu automatiquement quand il change (pas besoin de relancer uvicorn).

## Computer Use (Windows) — MVP contrôlé

Le worker supporte 2 familles d’actions via `context.desktop_action` :

- **Actions “MVP”** (déjà en place) : `open_url`, `notepad_append`, `open_app`
- **Actions “Computer Use”** (vision + souris/clavier) : `observe_screen`, `click_xy`, `move_xy`, `drag_xy`, `type_text`, `hotkey`, `scroll`, `wait_ms`
- **Macro** : `run_steps` (exécute une liste d’étapes bornée)
- **ComfyUI (API)** : `comfyui_queue`, `comfyui_patch_and_queue`, `comfyui_history`, `comfyui_view`

### Sécurité (important)

- **Désactivé par défaut** : `LBG_DESKTOP_COMPUTER_USE_ENABLED=0`
- **Dry-run** recommandé au début : `LBG_DESKTOP_DRY_RUN=1`
- **Approval token** conseillé en prod : `LBG_DESKTOP_APPROVAL_TOKEN=...`
- **Observation protégée** (par défaut si token activé) : `LBG_DESKTOP_OBSERVE_REQUIRES_APPROVAL=1`
- **Audit JSONL** : `LBG_DESKTOP_AUDIT_LOG_PATH=C:\Agent_IA\desktop_audit.jsonl`
- **ComfyUI** : désactivé par défaut + approval requis (`LBG_DESKTOP_COMFYUI_ENABLED=0`)

### Exemples de payloads (`POST /invoke`)

#### 1) Observe (dry-run)

```json
{
  "actor_id": "ui:desktop",
  "text": "",
  "context": {
    "desktop_dry_run": true,
    "desktop_action": { "kind": "observe_screen" }
  }
}
```

#### 2) Observe réel (avec approval)

```json
{
  "actor_id": "ui:desktop",
  "text": "",
  "context": {
    "desktop_dry_run": false,
    "desktop_approval": "CHANGE-MOI",
    "desktop_action": { "kind": "observe_screen", "region": { "x": 0, "y": 0, "w": 1280, "h": 720 } }
  }
}
```

#### 3) Click + type (dry-run)

```json
{
  "actor_id": "ui:desktop",
  "text": "remplir un champ",
  "context": {
    "desktop_dry_run": true,
    "desktop_action": { "kind": "click_xy", "x": 640, "y": 360, "button": "left", "clicks": 1 }
  }
}
```

### Paramètres supportés (Computer Use)

- `observe_screen`
  - `region` (optionnel) : `{x,y,w,h}`
  - retour contrôlé via `LBG_DESKTOP_SCREENSHOT_RETURN` :
    - `path` (défaut) : écrit dans `LBG_DESKTOP_SCREENSHOT_DIR` et renvoie le chemin
    - `base64` : renvoie aussi `base64` (coûteux)
    - `none` : n’expose pas l’image, audit uniquement
- `click_xy`
  - `x`, `y` (requis), `button` (`left|right|middle`), `clicks` (1..10), `interval_s`
- `move_xy`
  - `x`, `y` (requis), `duration_s` (0..10)
- `drag_xy`
  - `x1`,`y1`,`x2`,`y2` (requis), `duration_s`, `button`
- `type_text`
  - `text` (requis), `interval_s` (0..1), limite via `LBG_DESKTOP_TYPE_MAX_CHARS`
- `hotkey`
  - `keys` (requis) : `["ctrl","l"]`, `["ctrl","shift","i"]`, etc. (max 6)
- `scroll`
  - `clicks` (requis) : -2000..2000
- `wait_ms`
  - `ms` (requis) : 0..60000

### ComfyUI (API locale)

Ces actions appellent l’API ComfyUI (typiquement `http://127.0.0.1:8188`) depuis le worker Windows.
Elles sont protégées par :
- `LBG_DESKTOP_COMFYUI_ENABLED=1`
- `context.desktop_approval` (approval token)

Actions :
- `comfyui_queue` : envoie un workflow “API export” (payload `prompt`)
  - `workflow` (requis, objet JSON)
  - `client_id` (optionnel)
- `comfyui_patch_and_queue` : applique un patch simple puis queue
  - `workflow` (requis)
  - `ops` (requis) : liste d’opérations :
    - `set_input`: `{op:"set_input", node:"205", key:"seed", value:123}`
    - `set_inputs`: `{op:"set_inputs", node:"205", values:{...}}`
  - `client_id` (optionnel)
- `comfyui_history`
  - `prompt_id` (requis)
- `comfyui_view` : récupère un fichier depuis `/view`
  - `filename` (requis), `subfolder` (optionnel), `type` (optionnel, défaut `output`)
  - `return` : `path|base64|none` (défaut `path`) ; écrit dans `LBG_COMFYUI_DOWNLOAD_DIR` si `path`

### `run_steps` (macro)

Exécute une séquence bornée d’actions (utile côté orchestrateur : un seul appel).

- entrée :
  - `steps` : liste d’objets `{kind: "...", ...}` (les mêmes champs que les actions unitaires)
  - `stop_on_fail` (optionnel, défaut `true`) : si `false`, continue même si une étape échoue
- limites :
  - `LBG_DESKTOP_RUN_STEPS_MAX` (défaut 12)
  - `LBG_DESKTOP_RUN_STEPS_TIMEOUT_MS` (défaut 30000)
- audit :
  - un résumé `event: agents.desktop.audit` (kind=`run_steps`)
  - des sous-événements `event: agents.desktop.step` (un par étape)
- sortie :
  - `step_outputs[]` : sorties détaillées par étape (ex. screenshot `path/mime/bytes`)
  - `errors[]` : erreurs collectées (surtout utile quand `stop_on_fail=false`)

Exemple :

```json
{
  "desktop_action": {
    "kind": "run_steps",
    "steps": [
      { "kind": "open_url", "url": "https://example.org" },
      { "kind": "wait_ms", "ms": 800 },
      { "kind": "observe_screen" }
    ]
  }
}
```

