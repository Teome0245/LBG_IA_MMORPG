# Desktop (hybride) — VM orchestrateur + agent Windows

**Alignement produit** : ce flux implémente le **Mode A — `local_assistant`** décrit dans [`adr/0004-assistant-local-vs-persona-mmo.md`](adr/0004-assistant-local-vs-persona-mmo.md) (capability **`desktop_control`** → **`agent.desktop`** → worker HTTP Windows ou Linux).

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

### Proposition `DESKTOP_JSON` (LLM → validation humaine)

Pour rapprocher le flux du MMO (`ACTION_JSON`) sans exécuter à l’aveugle :

1. Sur l’agent dialogue HTTP : activer **`LBG_DIALOGUE_DESKTOP_PLAN=1`** (avec un LLM configuré).
2. Un appel `POST /invoke` avec **`context._desktop_plan`: true** utilise un prompt « planificateur desktop » ; le modèle peut émettre une première ligne **`DESKTOP_JSON: {"kind":...}`**.
3. Le serveur parse et sanitise la proposition, puis l’expose dans **`meta.desktop_action_proposal`** (les allowlists réelles restent au worker lors du routage). L’agent dialogue annonce **`desktop_plan_env_enabled`** dans **`GET /healthz`** (utile pour le bandeau diagnostique sur `#/desktop` via `GET /v1/pilot/status`).
4. Le Pilot (`#/desktop`) peut appeler **`POST /v1/pilot/agent-dialogue/invoke`** (proxy même origine), remplir le textarea `desktop_action`, puis l’opérateur clique **Envoyer** (`/v1/pilot/route`) après relecture.

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

### `search_web_open` (recherche web bornée)

Ouvre le navigateur sur une URL **HTTPS** construite en interne (pas d’URL arbitraire) :

- moteur **DuckDuckGo** par défaut (`https://duckduckgo.com/?q=…`) ;
- ou **Google** si `LBG_DESKTOP_SEARCH_ENGINE=google` (ou `LBG_LINUX_SEARCH_ENGINE=google` sur l’agent Linux).

**Activation** : `LBG_DESKTOP_WEB_SEARCH=1` (Windows / exécuteur Python `desktop_executor`) ou `LBG_LINUX_WEB_SEARCH=1` (linux_agent). **Désactivé par défaut** : tant que la variable n’est pas truthy, l’action renvoie `feature_disabled`.

Payload :

```json
{
  "desktop_action": {
    "kind": "search_web_open",
    "query": "site de machin"
  }
}
```

- `query` : obligatoire, tronquée à 220 caractères côté serveur.
- L’URL finale est validée par une **liste blanche de domaines** (duckduckgo.com / google.com selon le moteur) : pas besoin d’autoriser chaque requête dans `LBG_DESKTOP_URL_HOST_ALLOWLIST`.

Même **dry-run**, **approval** et **audit** que `open_url`.

### `mail_imap_preview` (IMAP INBOX, lecture seule, bornée)

Retourne un **JSON** avec en-têtes + `body_preview` pour les messages récents de l’**INBOX** qui matchent les filtres (sous-chaînes insensibles à la casse, **ET** logique si les deux sont fournis).

**Activation** : `LBG_DESKTOP_MAIL_ENABLED=1` (Windows / exécuteur `desktop_executor`) ou `LBG_LINUX_MAIL_ENABLED=1` (linux_agent). **Désactivé par défaut.**

**Configuration** (secrets — ne jamais mettre de mot de passe dans `desktop_action`) :

- `LBG_DESKTOP_MAIL_IMAP_HOST`, `LBG_DESKTOP_MAIL_IMAP_USER`, `LBG_DESKTOP_MAIL_IMAP_PASSWORD`
- `LBG_DESKTOP_MAIL_IMAP_PORT` (défaut 993), option `LBG_DESKTOP_MAIL_IMAP_NO_SSL=1` pour lab sans TLS (déconseillé)

Équivalents Linux : `LBG_LINUX_MAIL_*`.

Payload :

```json
{
  "desktop_action": {
    "kind": "mail_imap_preview",
    "from_contains": "intel",
    "subject_contains": "facture",
    "max_messages": 3,
    "max_body_chars": 800,
    "max_scan": 200
  }
}
```

- `from_contains` / `subject_contains` : au moins **un** des deux obligatoire.
- `max_messages` : 1–10 (défaut 3) ; `max_body_chars` : 0–4000 (défaut 800) ; `max_scan` : nombre max de UIDs récents examinés (10–500, défaut 200).
- Dossier **INBOX uniquement** en MVP (`folder` autre valeur → refus).

Sortie typique : `outcome: ok|dry_run|error|configuration_error|feature_disabled`, champ **`messages`** (liste `uid`, `from`, `subject`, `date`, `body_preview`).

Le module partagé `mail_imap_preview.py` est copié sous `agents/src/lbg_agents/` et les répertoires `windows_agent/Agent_IA/` / `linux_agent/Agent_IA/` — **à resynchroniser** si tu modifies la logique IMAP.

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

## Computer Use (vision + souris/clavier) — MVP contrôlé

En plus des actions MVP, le worker Windows supporte un sous-ensemble “Computer Use” (interaction UI) **sur actions structurées uniquement**.

### Activation (Windows)

- Feature flag : `LBG_DESKTOP_COMPUTER_USE_ENABLED=1` (sinon refus `feature_disabled`)
- Débuter en `LBG_DESKTOP_DRY_RUN=1` puis basculer en réel
- Recommandé en prod : `LBG_DESKTOP_APPROVAL_TOKEN=...` + audit JSONL

### Actions unitaires (`context.desktop_action.kind`)

- `observe_screen` : capture écran (retour `path`/`base64`/`none`)
- `click_xy`, `move_xy`, `drag_xy`
- `type_text`, `hotkey`, `scroll`, `wait_ms`

Notes sécurité :
- `observe_screen` peut exiger un token même si c’est “juste” une capture : `LBG_DESKTOP_OBSERVE_REQUIRES_APPROVAL=1`
- `type_text` est borné : `LBG_DESKTOP_TYPE_MAX_CHARS`
- les coordonnées sont validées (doivent être dans l’écran)

### Macro `run_steps` (un seul appel = plusieurs actions)

But : côté orchestrateur, envoyer une **séquence bornée** en une requête.

Entrée :
- `steps` : liste d’objets `{kind: "...", ...}` (mêmes champs que les actions unitaires)
- `stop_on_fail` (optionnel, défaut `true`) : si `false`, continue malgré une erreur

Limites :
- `LBG_DESKTOP_RUN_STEPS_MAX` (défaut 12)
- `LBG_DESKTOP_RUN_STEPS_TIMEOUT_MS` (défaut 30000)

Sortie :
- `results[]` : statut minimal par étape
- `step_outputs[]` : sorties détaillées par étape (ex. screenshot `path/mime/bytes`)
- `errors[]` : erreurs collectées (utile quand `stop_on_fail=false`)

Audit :
- `agents.desktop.step` : un événement par étape
- `agents.desktop.audit` : résumé (kind=`run_steps`)

Exemple :

```json
{
  "desktop_action": {
    "kind": "run_steps",
    "stop_on_fail": false,
    "steps": [
      { "kind": "open_url", "url": "https://example.org" },
      { "kind": "wait_ms", "ms": 800 },
      { "kind": "observe_screen" }
    ]
  }
}
```

## Recettes PowerShell (smoke)

Pré-requis :
- le worker Windows est démarré (par défaut `http://127.0.0.1:5005`)
- `desktop.env` est configuré (feature flags / allowlists / token)

Astuce : l’approval token n’est requis que si `LBG_DESKTOP_APPROVAL_TOKEN` est défini ; `observe_screen` peut aussi exiger un token selon `LBG_DESKTOP_OBSERVE_REQUIRES_APPROVAL`.

### 1) Healthz (diagnostic rapide)

```powershell
Invoke-RestMethod http://127.0.0.1:5005/healthz | ConvertTo-Json -Depth 10
```

### 2) Dry-run (aucune action réelle)

```powershell
$body = @{
  actor_id = "test"
  text = ""
  context = @{
    desktop_dry_run = $true
    desktop_action = @{ kind = "click_xy"; x = 100; y = 100; button = "left"; clicks = 1 }
  }
} | ConvertTo-Json -Depth 10

Invoke-RestMethod http://127.0.0.1:5005/invoke -Method Post -ContentType "application/json" -Body $body | ConvertTo-Json -Depth 12
```

### 3) Réel (click) — avec approval si activé

```powershell
$body = @{
  actor_id = "test"
  text = ""
  context = @{
    desktop_dry_run = $false
    desktop_approval = "CHANGE-MOI"
    desktop_action = @{ kind = "click_xy"; x = 100; y = 100; button = "left"; clicks = 1 }
  }
} | ConvertTo-Json -Depth 10

Invoke-RestMethod http://127.0.0.1:5005/invoke -Method Post -ContentType "application/json" -Body $body | ConvertTo-Json -Depth 12
```

### 4) `run_steps` (open_url → wait → observe) — récupère le screenshot path

```powershell
$body = @{
  actor_id = "test"
  text = ""
  context = @{
    desktop_dry_run = $false
    desktop_approval = "CHANGE-MOI"
    desktop_action = @{
      kind = "run_steps"
      stop_on_fail = $false
      steps = @(
        @{ kind = "open_url"; url = "https://example.org" },
        @{ kind = "wait_ms"; ms = 800 },
        @{ kind = "observe_screen" }
      )
    }
  }
} | ConvertTo-Json -Depth 12

$r = Invoke-RestMethod http://127.0.0.1:5005/invoke -Method Post -ContentType "application/json" -Body $body
$r.step_outputs[-1].path
$r.errors | ConvertTo-Json -Depth 8
```

## ComfyUI (API locale) — câblage par JSON (recommandé)

Si ComfyUI tourne sur le même PC Windows (souvent `http://127.0.0.1:8188`), le worker Windows peut appeler l’API
localement et “câbler” un workflow **en modifiant le JSON** (export “API”) plutôt que par manipulation UI.

Actions `desktop_action.kind` :
- `comfyui_queue`
- `comfyui_patch_and_queue`
- `comfyui_history`
- `comfyui_view`

Sécurité :
- activer `LBG_DESKTOP_COMFYUI_ENABLED=1`
- approval requis (`context.desktop_approval`)

### Smoke “ComfyUI via worker Windows”

Le repo inclut un smoke PowerShell qui pilote ComfyUI **via** l’agent Windows (API ComfyUI), sans UI automation :

- Script : `infra/scripts/smoke_comfyui.ps1`
- Il attend un workflow ComfyUI **exporté en JSON “API”** (menu ComfyUI : exporter pour API), puis :
  - queue (optionnel : patch `seed`)
  - poll `history`
  - download du 1er output via `comfyui_view`

Exemple (sur Windows, là où tourne le worker `Agent_IA`) :

```powershell
.\infra\scripts\smoke_comfyui.ps1 `
  -BaseUrl "http://127.0.0.1:5005" `
  -Approval "<TOKEN_SI_ACTIF>" `
  -WorkflowPath "C:\Agent_IA\workflows\bourg_api.json" `
  -SeedNode "3" `
  -Seed 42
```

### Smoke “ComfyUI 2-pass” (terrain puis bâtiments)

Pour un rendu plus contrôlé (style fort sans inventer de bâtiments), exécuter 2 passes :
- **Pass 1** : fond nature (herbe, arbres, rochers) — ControlNet **routes** désactivé (`strength: 0`) ; bâtiments guidés par Canny sur `buildings.png`
- **Pass 2** : affiner les **bâtiments** uniquement (masque) ; prompts sans incitation aux chemins ni au village

Script : `infra/scripts/smoke_comfyui_2pass.ps1`

Exemple :

```powershell
.\infra\scripts\smoke_comfyui_2pass.ps1 `
  -BaseUrl "http://127.0.0.1:5005" `
  -Approval "<TOKEN_SI_ACTIF>" `
  -WorkflowPass1Path "C:\Agent_IA\workflows\Map_mmo.json" `
  -WorkflowPass2Path "C:\Agent_IA\workflows\Map_mmo_pass2_buildings.json" `
  -ComfyInputDir "C:\Users\sdesh\ComfyUI\input" `
  -Pass1OutputAsInputName "bourg.png" `
  -SeedPass1 42 `
  -SeedPass2 43
```

**Depuis WSL (bash)** : lancer PowerShell Windows avec les chemins du repo convertis automatiquement :

```bash
cd LBG_IA_MMO/infra/scripts
export LBG_DESKTOP_BASE_URL="http://192.168.0.10:5005"   # agent Windows (obligatoire si défaut auto faux)
export LBG_DESKTOP_APPROVAL="CHANGE-MOI"                   # si approval actif
./run_smoke_comfyui_2pass_wsl.sh
```

Sans `LBG_DESKTOP_BASE_URL`, le script utilise `http://<nameserver resolv.conf>:5005` (souvent l’hôte Windows sous WSL2). Les workflows par défaut sont `Boite à idées/Map_mmo.json` et `Map_mmo_pass2_buildings.json` ; sinon définir `WF_PASS1` / `WF_PASS2` (chemins absolus WSL).

**Même chose mais workflows déjà copiés sous `C:\Agent_IA\workflows\`** (script PS1 sur `C:\Agent_IA\`) — équivalent de ta commande one-liner :

```bash
./run_smoke_comfyui_2pass_agent_ia.sh
# ou : LBG_DESKTOP_APPROVAL=xxx COMFY_INPUT_DIR='C:/Users/autre/ComfyUI/input' ./run_smoke_comfyui_2pass_agent_ia.sh
```

#### État carte MMO — pipeline 2 passes (point situation **2026-05-02**, pause)

**Objectif visuel (en cours)**  
- Les **gros bâtiments** sont jugés corrects dans l’ensemble.  
- Le **remplissage hors bâtiments** doit rester **clair** : herbe, arbres, rochers — **sans** petit village, **sans** réseau de chemins, cadre moins “carte de bourg saturée”.

**Ce qui fonctionne techniquement**  
- Le smoke **`smoke_comfyui_2pass.ps1`** peut aller au bout : pass 1 → copie `bourg.png` → pass 2 → fichier final sous `ComfyUI\output` (préfixes `lbg_map_pass1_*` / `lbg_map_pass2_*`).  
- Fallback **fichier sur disque** si `/history` est vide ou peu fiable (voir ci‑dessous).  
- Scripts : `infra/scripts/smoke_comfyui.ps1`, `infra/scripts/smoke_comfyui_2pass.ps1`.  
- Workflows API dans le repo :  
  - `Boite à idées/Map_mmo.json` — pass 1  
  - `Boite à idées/Map_mmo_pass2_buildings.json` — pass 2  

**Modifs déjà dans le repo (pass 1)** — à **recopier** sur Windows si tu testes depuis `C:\Agent_IA\workflows\` :  
- Prompt positif : prairie / cailloux / arbres épars, **interdiction explicite** de routes et hameaux ; conserve la consigne “layout des bâtiments inchangé”.  
- Prompt négatif : ajout de termes **roads, paths, trails, dirt tracks**, etc.  
- Chaîne sampler : `213/214 → 209` (Canny sur **`buildings.png`**) → **`215`** (image **`roads.png`**). Le node **`215`** a **`strength: 0.0`** pour **ne plus imposer** le graphe de routes via ControlNet tout en gardant l’étape dans le graphe.

**Constat (tests visuels)**  
- Le rendu peut rester **chargé** (micro-maisons, chemins). Causes possibles : décalage **copie locale Windows** vs repo ; **IP‑Adapter** / référence style ; limites du modèle. Les prompts **pass 2** dans le repo ont été alignés (plus de fusion « grass and paths », négatif routes/village) — **à re-tester** après sync des JSON vers `C:\Agent_IA\workflows\`.

**Contraintes déjà documentées (rappel)**  
- **PowerShell depuis WSL** : une ligne ou `\` en continuation, pas les backticks Windows depuis bash.  
- **Approval token** si `approval_gate_active` sur le worker.  
- **IP‑Adapter preset** : valeur exacte du dropdown (ex. `STANDARD (medium strength)`).  
- **LoadImage** : tous les fichiers référencés doivent exister dans `ComfyUI\input`.  
- **`ImageToMask`** : renseigner `channel` (ex. `red`).  
- **`smoke_comfyui_2pass.ps1`** : parsing `history` tolérant ; timeout large (`TimeoutS` défaut élevé) ; fallback **attente fichier** sous `ComfyUI\output`.

**Reprise / itération**  
1. Copier **`Map_mmo.json`** et **`Map_mmo_pass2_buildings.json`** du repo vers `C:\Agent_IA\workflows\` (ou chemins passés à `-WorkflowPass1Path` / `-WorkflowPass2Path`).  
2. **Isoler pass 1** : juger le PNG `lbg_map_pass1_*` seul avant pass 2.  
3. Si le fond reste trop “bourg” : baisser **IP‑Adapter** (pass 1 / pass 2 selon graphe) ou changer la **référence** image.  
4. Option ultérieure : passe “nettoyage fond” (inpaint / dénoise **hors bâtiments** uniquement).


## `desktop.env` (config hot-reload)

Sur Windows, la configuration est lue depuis `C:\Agent_IA\desktop.env` (chemin donné par `LBG_DESKTOP_ENV_PATH`).
Elle est **rechargée automatiquement** quand le fichier change (pas besoin de relancer uvicorn) :
- allowlists (URLs/hosts/fichiers/apps)
- dry-run
- approval token (si utilisé)
- choix d’éditeur (Notepad++ / Word / défaut)
 - paramètres Computer Use (feature flag, screenshots, limites, run_steps)

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
- `LBG_DESKTOP_COMPUTER_USE_ENABLED` : `1` pour activer les actions UI (sinon refus)
- `LBG_DESKTOP_OBSERVE_REQUIRES_APPROVAL` : `1` pour exiger un token sur `observe_screen`
- `LBG_DESKTOP_SCREENSHOT_DIR` : ex. `C:\Agent_IA\screenshots`
- `LBG_DESKTOP_SCREENSHOT_RETURN` : `path|base64|none` (défaut `path`)
- `LBG_DESKTOP_SCREENSHOT_MAX_WIDTH` : ex. `1280`
- `LBG_DESKTOP_SCREENSHOT_FORMAT` : `jpeg|png` (défaut `jpeg`)
- `LBG_DESKTOP_SCREENSHOT_JPEG_QUALITY` : ex. `65`
- `LBG_DESKTOP_TYPE_MAX_CHARS` : ex. `400`
- `LBG_DESKTOP_RUN_STEPS_MAX` : ex. `12`
- `LBG_DESKTOP_RUN_STEPS_TIMEOUT_MS` : ex. `30000`
 - `LBG_DESKTOP_COMFYUI_ENABLED` : `1` pour activer les actions ComfyUI
 - `LBG_COMFYUI_BASE_URL` : `http://127.0.0.1:8188`
 - `LBG_COMFYUI_TIMEOUT_S` : ex. `120`
 - `LBG_COMFYUI_DOWNLOAD_DIR` : ex. `C:\Agent_IA\comfyui_downloads`

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

- Pas d’autres dossiers IMAP que **INBOX** ; pas d’écriture (envoi, marquage lu, suppression) via ce canal.
- `notepad_append` est un “pont” simple ; l’UI automation avancée nécessitera une lib dédiée (ex. Playwright/WinAppDriver/Power Automate, etc.) et une modélisation d’actions plus riche.

