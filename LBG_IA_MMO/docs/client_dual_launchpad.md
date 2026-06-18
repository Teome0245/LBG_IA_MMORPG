# Clients dual PreCu / Prime — LBG Launchpad

Décisions produit (2026-05-28), suite au plan dual-client.

## Décisions validées

| # | Sujet | Choix |
|---|--------|--------|
| 1 | Binaires | **Deux builds distincts** — PreCu : `SWGEmu.exe` ; Prime : **`lbgemu.exe`** (même rôle, nom différent pour éviter les confusions). |
| 2 | Hébergement patches | **VM 245** (`:8080` ou dédié) ; **copie miroir sur NAS** si place disque suffisante. |
| 3 | Installation poste joueur | **Install complète ×2** (~15–20 Go chacune) ; le launchpad affiche un **avertissement taille disque** avant bootstrap / copie. |
| 4 | Contenu Prime | **TRE custom** + **binaire client custom** (`lbgemu.exe` + éventuelles DLL associées). |
| 5 | Launchpad SWGEmu | Objectif : **ne plus en dépendre** ; LBG Launchpad reprend intégrité MD5 + patch par canal. |
| 6 | Client actuel | `J:\swgemu\StarWarsGalaxies` (ou équivalent) = référence **Original PreCu** — compatible des deux serveurs aujourd’hui ; on le **fige** comme base `precu-original` sans le modifier pour Prime. |

## Arborescence cible

```
swgemu/
├── dist/                              # LBG Launchpad seul
│   ├── LBG Launchpad.exe
│   └── launchpad.config.json
├── clients/
│   ├── precu-original/                # Copie figée de StarWarsGalaxies actuel
│   │   ├── SWGEmu.exe
│   │   ├── swgemu.cfg
│   │   └── …
│   └── prime-lbg/
│       ├── lbgemu.exe                 # Build Prime dédié
│       ├── swgemu.cfg                 # -s swgemu.cfg inchangé (nom cfg standard)
│       ├── custom_*.tre               # Patches données
│       └── …
└── packages/                          # (optionnel) zips bootstrap LAN / NAS
```

**Migration initiale**

1. Copier `StarWarsGalaxies` → `clients/precu-original` (ne plus patcher ce dossier pour Prime).
2. Copier `clients/precu-original` → `clients/prime-lbg`.
3. Sur `prime-lbg` uniquement : remplacer exe par `lbgemu.exe`, ajouter TRE / cfg, ajuster `swgemu_login.cfg` (port Prime).

## Launchpad — config v2 (schéma)

```json
{
  "launchpadVersion": "2.0.0",
  "statusApiUrl": "http://192.168.0.245:8792/api/servers",
  "patchServerUrl": "http://192.168.0.245:8080",
  "patchServerUrlNas": "http://<nas>/swg-patches",
  "diskSpaceWarningGb": 40,
  "profiles": [
    {
      "id": "precu",
      "label": "SWGEmu PreCu (original)",
      "gameDir": "J:\\swgemu\\clients\\precu-original",
      "gameExe": "SWGEmu.exe",
      "configFile": "swgemu.cfg",
      "patchChannel": "precu",
      "servers": [{ "id": "precu", "ip": "192.168.0.245", "loginPort": 44453 }]
    },
    {
      "id": "prime",
      "label": "LBG Prime",
      "gameDir": "J:\\swgemu\\clients\\prime-lbg",
      "gameExe": "lbgemu.exe",
      "configFile": "swgemu.cfg",
      "patchChannel": "prime",
      "servers": [{ "id": "prime", "ip": "192.168.0.246", "loginPort": 44553 }]
    }
  ]
}
```

Lancement : `spawn(gameExe, ['-s', configFile], { cwd: gameDir })` — déjà le modèle dans `new_mmo/launchpad/main.js`.

## Serveur de patches (VM 245 + NAS)

```
http://192.168.0.245:8080/patches/precu/manifest.json
http://192.168.0.245:8080/patches/prime/manifest.json
```

- **precu** : `SWGEmu.exe`, hotfix SWGEmu, templates `swgemu_login.cfg` (44453).
- **prime** : `lbgemu.exe`, TRE custom, mêmes règles d’intégrité MD5.

Sync NAS : rsync / cron depuis 245 après chaque publication (miroir lecture seule pour secours bande passante).

## UI Launchpad — message espace disque

Avant première install ou « Installer les deux clients » :

> Environ **40 Go libres** recommandés (2 installations complètes ~15–20 Go chacune + marge patches).

Vérification optionnelle : `fs.statfs` / WMI espace libre sur le lecteur cible.

## Phases d’implémentation

| Phase | Livrable | Statut |
|-------|----------|--------|
| P0 | Profils `precu` / `prime` dans `new_mmo/launchpad` + migration config + avertissement disque | **Fait** (v2.0.0) |
| P1 | Manifests `patches/precu` et `patches/prime` sur VM 245 | **Fait** (`generate_client_patch_manifests.sh`, 6+8 fichiers) |
| P2 | Vérif MD5 type `required2.txt` par canal | À faire |
| P3 | Déploiement autre PC (robocopy + config relative) | **Fait** (`infra/scripts/deploy_client_new_pc.ps1`) |
| P4 | Repo `client-prime-patches` + CI manifest |
| P5 | Retrait launchpad SWGEmu du flux joueur |

## Scripts ops

| Script | Rôle |
|--------|------|
| `infra/scripts/generate_client_patch_manifests.sh` | Copie exe/cfg depuis `SWG_ROOT`, MD5 → `infra/client-patch-server/patches/{precu,prime}/` |
| `infra/scripts/install_client_patch_server_245.sh` | rsync patches → VM `:8080` |
| `infra/scripts/deploy_client_new_pc.ps1` | PC vierge : robocopy launchpad + 2 clients, `launchpad.config.json`, patches HTTP |

Exemple nouveau PC (PowerShell admin) :

```powershell
.\deploy_client_new_pc.ps1 -SourceRoot \\192.168.0.245\swgemu -TargetRoot D:\swgemu
```

## Sources code

- Launchpad Electron : `new_mmo/launchpad/`
- Build Windows : `npm run build:win` → copier vers `swgemu/dist/`
- Doc serveurs : `docs/core3_ia_prime_tatooine.md`

## Démarrage rapide (lbgemu / Prime uniquement)

Dans `clients/prime-lbg/` (pas PreCu) :

- `user.cfg` + `lbgemu_client.cfg` : `skipSplash=1`, `disableCutScenes=1` ([wiki SWG](https://swg.fandom.com/wiki/How_to_disable_the_splash_screens))
- `swgemu_live.cfg` : `messageOfTheDayTable` commenté (bandeau texte login)
- Modèles versionnés : `new_mmo/client-prime-lbg/`

## Hors scope

- Junctions TRE partagés (optimisation disque ultérieure).
- Lien Salesforce / outils internes non liés au client SWG.
