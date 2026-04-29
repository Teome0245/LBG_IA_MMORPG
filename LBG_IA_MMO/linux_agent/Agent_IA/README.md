# Agent Linux (Agent_IA)

Worker Linux (HTTP) sur le même modèle que le worker Windows `windows_agent/Agent_IA`, mais adapté à Linux.

## But

Exécuter des actions "host tools" **sous contrôle** via :
- actions structurées (`context.desktop_action`)
- allowlists
- dry-run
- approval token (optionnel)
- audit JSONL
- configuration **hot-reload** via `linux.env`

## Endpoints

- `GET /healthz`
- `POST /invoke` (entrée `actor_id`, `text`, `context` ; attend `context.desktop_action`)

## Config hot-reload

Par défaut, l’agent lit `linux.env` dans son répertoire de travail. Tu peux surcharger :
- `LBG_LINUX_ENV_PATH=/chemin/vers/linux.env`

Le fichier est relu automatiquement quand il change (mtime).

## Actions MVP

### `open_url`

```json
{
  "desktop_action": { "kind": "open_url", "url": "https://example.org" }
}
```

Allowlist :
- `LBG_LINUX_URL_ALLOWLIST` (URLs exactes, strict)
- `LBG_LINUX_URL_HOST_ALLOWLIST` (domaines/hosts, recommandé)

### `file_append`

Append du texte dans un fichier allowlisté.

```json
{
  "desktop_action": { "kind": "file_append", "path": "/tmp/lbg_notes.txt", "text": "hello\n" }
}
```

Allowlist :
- `LBG_LINUX_FILE_ALLOWLIST_DIRS` : répertoires parents autorisés (CSV)

### `open_app` (générique)

Lance une application allowlistée.

```json
{
  "desktop_action": { "kind": "open_app", "app": "htop", "args": [], "learn": false }
}
```

Allowlist + mapping :
- `LBG_LINUX_APP_ALLOWLIST`
- `LBG_LINUX_APP_MAP_JSON` (id → commande)

Apprentissage contrôlé (optionnel) :
- `LBG_LINUX_LEARN_ENABLED=1` + `"learn": true`
- résolution via `which` (`shutil.which`)
- persist dans `linux.env` (mapping + allowlist)

## Lancer localement

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 6001
```

## Tests

```bash
python3 -m unittest -v
```

