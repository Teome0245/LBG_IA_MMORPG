# Desktop (hybride) — VM orchestrateur + agent Windows

## Objectif

Permettre à une IA « incarnée » de **déclencher des actions sur un PC Windows** (UI automation / navigateur / fichiers),
en gardant un **cerveau central** côté VM (orchestrateur) et en déléguant l’exécution à un **worker HTTP** sur la machine Windows.

Cette approche vise un MVP **contrôlé** :
- pas d’exécution sur texte libre
- **actions structurées**
- **allowlists**
- **dry-run par défaut**
- **approval token** optionnel
- **audit JSONL**

## Topologie

- **Backend** (VM core) : sert `/pilot/` + API `/v1/pilot/route`
- **Orchestrateur** (VM core) : route les intentions vers une capability
- **Agents** (VM core) : `lbg_agents.dispatch` exécute le handler `agent.desktop`
- **Agent Desktop Windows** : service HTTP (port typique 5005 chez toi) qui exécute réellement sur Windows

Flux :
1. UI `/pilot/#/desktop` envoie `POST /v1/pilot/route` au backend
2. Backend forward → orchestrateur
3. Orchestrateur : si `context.desktop_action` est présent, route vers intent `desktop_control` → `agent.desktop`
4. `agent.desktop` appelle `POST {LBG_AGENT_DESKTOP_URL}/invoke` (worker Windows)
5. Worker applique gardes + exécute + renvoie un résultat structuré + écrit un audit

## Module Windows dans le repo + sync vers `C:\Agent_IA`

Le worker Windows est désormais un **module du repo** :
- Source : `windows_agent/Agent_IA/`
- Cible runtime sur ton PC : `C:\Agent_IA\`

Pour garder `C:\Agent_IA` à jour depuis WSL (sans copier à la main) :

```bash
bash LBG_IA_MMO/infra/scripts/sync_windows_agent.sh
```

## Capability et routage

- Capability orchestrateur : **`desktop_control`**
- Routage forcé **uniquement** si `context.desktop_action` est un objet JSON
  - But : éviter les faux positifs (« ouvre notepad… » dans une discussion ne doit pas exécuter)

## Actions MVP

### 1) `open_url`

Ouvre une URL dans le navigateur par défaut (worker Windows).

```json
{
  "desktop_action": {
    "kind": "open_url",
    "url": "https://example.org"
  }
}
```

Contrôle :
- soit `url` est **exactement** dans `LBG_DESKTOP_URL_ALLOWLIST` (mode strict),
- soit le host de `url` matche un domaine/host dans `LBG_DESKTOP_URL_HOST_ALLOWLIST` (recommandé).

### 2) `notepad_append`

Append du texte dans un fichier, puis ouvre un éditeur sur ce fichier (best-effort).

```json
{
  "desktop_action": {
    "kind": "notepad_append",
    "path": "C:\\Users\\Public\\lbg_desktop.txt",
    "text": "Hello\\n"
  }
}
```

Contrôle : `path` doit être sous un répertoire autorisé par `LBG_DESKTOP_FILE_ALLOWLIST_DIRS`.

Éditeur : configurable côté Windows via :
- `LBG_DESKTOP_EDITOR=notepad` | `notepad++` | `word` | `default`
- `LBG_DESKTOP_NOTEPADPP_PATH` (optionnel) : chemin absolu `notepad++.exe`
- `LBG_DESKTOP_WORD_PATH` (optionnel) : chemin absolu `WINWORD.EXE`

### 3) `open_app` (générique)

Lance une application allowlistée.

```json
{
  "desktop_action": {
    "kind": "open_app",
    "app": "vlc",
    "args": []
  }
}
```

Contrôle :
- `app` doit être dans `LBG_DESKTOP_APP_ALLOWLIST`
- la commande est définie par `LBG_DESKTOP_APP_MAP_JSON` (id → commande)

Apprentissage contrôlé (optionnel) :
- si `LBG_DESKTOP_LEARN_ENABLED=1` et que l’action contient `"learn": true`,
  l’agent peut tenter de **résoudre automatiquement** le chemin (via resolver Windows)
  et **mettre à jour `desktop.env`** (mapping + allowlist).
- recommandé de garder un `LBG_DESKTOP_APPROVAL_TOKEN` actif pour toute exécution réelle.

## `desktop.env` (config hot-reload)

Sur Windows, la configuration est lue depuis `C:\Agent_IA\desktop.env` (chemin donné par `LBG_DESKTOP_ENV_PATH`).
Elle est **rechargée automatiquement** quand le fichier change (pas besoin de relancer uvicorn) :
- allowlists (URLs/hosts/fichiers/apps)
- dry-run
- approval token (si utilisé)
- choix d’éditeur (Notepad++ / Word / défaut)

## Gardes-fous (sécurité / contrôle)

### 1) Allowlists

Sans allowlist, **tout est refusé** (comportement volontaire).

- `LBG_DESKTOP_URL_ALLOWLIST` : URLs exactes autorisées (strict)
- `LBG_DESKTOP_URL_HOST_ALLOWLIST` : domaines/hosts autorisés (recommandé)
- `LBG_DESKTOP_FILE_ALLOWLIST_DIRS` : répertoires parents autorisés

### 2) Dry-run

Par défaut recommandé : **dry-run**.

- `LBG_DESKTOP_DRY_RUN=1` : aucune exécution réelle
- `context.desktop_dry_run=true` : dry-run pour un appel (si env ne l’a pas déjà activé)

### 3) Approval token (optionnel)

Si `LBG_DESKTOP_APPROVAL_TOKEN` est défini, toute exécution **réelle** exige :

```json
{
  "desktop_approval": "…token…"
}
```

Le token n’est pas journalisé dans l’audit.

### 4) Audit JSONL

Le worker écrit un audit (une ligne JSON par action) :
- stdout (par défaut) contrôlé via `LBG_DESKTOP_AUDIT_STDOUT`
- fichier JSONL (append) via `LBG_DESKTOP_AUDIT_LOG_PATH`

## Variables d’environnement

### Côté VM (orchestrateur / dispatch)

- `LBG_AGENT_DESKTOP_URL` : base URL du worker Windows (ex. `http://192.168.0.50:8060`)

### Côté Windows (worker)

- `LBG_DESKTOP_URL_ALLOWLIST` : `https://example.org,https://www.google.com` (strict)
- `LBG_DESKTOP_URL_HOST_ALLOWLIST` : `google.com,example.org` (recommandé)
- `LBG_DESKTOP_FILE_ALLOWLIST_DIRS` : `C:\Users\<toi>\Desktop,C:\Users\<toi>\Documents`
- `LBG_DESKTOP_DRY_RUN` : `1` recommandé au début
- `LBG_DESKTOP_APPROVAL_TOKEN` : (optionnel) token d’approbation
- `LBG_DESKTOP_AUDIT_LOG_PATH` : (optionnel) chemin d’audit JSONL
- `LBG_DESKTOP_AUDIT_STDOUT` : `0` pour désactiver stdout

## Mise en route (MVP)

### 1) Lancer le worker sur Windows

Sur ton poste, le module `windows_agent/Agent_IA` est copié dans `C:\Agent_IA` puis lancé avec :

```powershell
C:\Agent_IA\run_agent.cmd
```

### 2) Configurer la VM core

Dans `/etc/lbg-ia-mmo.env` (ou `infra/secrets/lbg.env` puis `push_secrets_vm.sh`) :

- `LBG_AGENT_DESKTOP_URL="http://<IP_WINDOWS>:8060"`

### 3) Tester depuis l’UI

Aller sur `/pilot/#/desktop`, garder `desktop_dry_run: true`, et cliquer sur **open_url**.

## Recettes “smoke” (payloads)

### Route (dry-run)

```json
{
  "actor_id": "ui:desktop",
  "text": "ouvre example",
  "context": {
    "desktop_dry_run": true,
    "desktop_action": { "kind": "open_url", "url": "https://example.org" },
    "history": []
  }
}
```

### Route (réel + approval)

```json
{
  "actor_id": "ui:desktop",
  "text": "ouvre example",
  "context": {
    "desktop_dry_run": false,
    "desktop_approval": "CHANGE-MOI",
    "desktop_action": { "kind": "open_url", "url": "https://example.org" }
  }
}
```

## Limites connues (MVP)

- Pas de lecture mail / navigateur contrôlé finement (à concevoir après stabilisation des gardes).
- `notepad_append` est un “pont” simple ; l’UI automation avancée nécessitera une lib dédiée (ex. Playwright/WinAppDriver/Power Automate, etc.) et une modélisation d’actions plus riche.

