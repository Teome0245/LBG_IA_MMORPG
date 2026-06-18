# Core3 (MMOCoreORB) sur la VM — sync, build, lancement

Ce document décrit le **serveur jeu SWGEmu Core3** (`MMOCoreORB`), distinct des services Python **`mmo_server`** / **`mmmorpg_server`** déployés par `infra/scripts/deploy_vm.sh`. Les sources vivent dans le dépôt **`new_mmo`** (chemin relatif typique : `lbg-mmo/Core3/MMOCoreORB`).

## 1. `login3` et `core3` : quoi lancer ?

- **`core3`** : unique **exécutable** du serveur (zone, persistance, etc.). Après compilation CMake, il est copié automatiquement vers `MMOCoreORB/bin/core3` (répertoire de travail attendu au runtime).
- **`login3`** : **bibliothèque statique** CMake (`src/server/login/`), liée **dans** `core3`. Il n’existe **pas** de binaire `login3` à lancer à part. Le **serveur login** est démarré **par `core3`** lorsque `MakeLogin = 1` dans `bin/conf/config.lua` (défaut).

En pratique : tu ne lances que **`./core3`** depuis `bin/` ; le module login (code `login3`) tourne **dans le même processus**.

## 2. Synchroniser les sources vers la VM

Depuis `LBG_IA_MMO/` sur le poste de dev :

```bash
# Exemple : VM MMO LAN 245, dépôt new_mmo à côté de projects/
export LBG_NEW_MMO_VM_HOST=192.168.0.245
export LBG_NEW_MMO_REPO=/chemin/absolu/vers/new_mmo   # si l’auto-détection ne suffit pas
bash infra/scripts/rsync_new_mmo_core3_orb.sh
```

Le script pousse vers un **staging** sous `~/.deploy/new_mmo/MMOCoreORB/`, puis **promouut** vers `/opt/lbg-new-mmo/MMOCoreORB` (sudo). Variables détaillées : en-tête de `infra/scripts/rsync_new_mmo_core3_orb.sh`.

## 3. Dépendances de build sur la VM (rappel)

Exemple Debian/Ubuntu : toolchain, `cmake`, `liblua5.3-dev`, **`libmariadb-dev`** (ou équivalent client MariaDB), `libssl-dev`, `zlib1g-dev`, `libdb-dev`, Java pour l’IDL, Boost, etc. (voir aussi `Core3/README.md` dans `new_mmo`).

Compilation typique **sur la VM** :

```bash
cd /opt/lbg-new-mmo/MMOCoreORB
rm -rf build && mkdir build && cd build
cmake -DCMAKE_BUILD_TYPE=Release ..
cmake --build . -j"$(nproc)"
```

Pour un binaire **plus portable** entre CPU (évite `-march=native` trop spécifique), utiliser l’option documentée dans le CMake du projet, par ex. **`cmake -DENABLE_NATIVE=OFF ..`** si disponible, puis rebuild.

## 4. Checklist runtime (ordre logique)

Quatre éléments à avoir ensemble pour un démarrage **stable** et **jouable** :

| # | Élément | Obligatoire | Rôle |
|---|---------|-------------|------|
| 1 | **Fichiers `.tre`** (client SWG, liste alignée avec `TreFiles` dans `config.lua`) | Oui | Datatables, IFF, skills, professions, tout passe par les archives ; sans elles : erreurs `TreeFile`, `SkillManager` vide, risque de **segfault** dans le chargement joueur. |
| 2 | **`bin/conf/config-local.lua`** | Oui | Surcharge **`TrePath`**, **DB**, etc., sans toucher `config.lua` (non réécrasé exactement comme tel si tu ne le commites pas dans les sources rsync — sur la VM le fichier local survit aux rsync tant qu’il n’est pas dans l’arborescence poussée). Modèle : `infra/snippets/core3-config-local.lua.example`. |
| 3 | **MariaDB** : base `swgemu`, schéma importé (`sql/swgemu.sql`), utilisateur **`DBUser`@localhost avec mot de passe = `DBPass`** | Oui | Sinon **`1045`** puis **`[Core] FATAL`**. Exemple : `ALTER USER 'swgemu'@'localhost' IDENTIFIED BY '…';` |
| 4 | **`conf/rev.txt`** | Optionnel (propreté des logs) | Évite le warning au démarrage ; ex. `echo "custom-build" > bin/conf/rev.txt`. |

### 4.1 Déployer les `.tre` depuis le dépôt `new_mmo`

Les fichiers du client peuvent être présents sous **`new_mmo/StarWarsGalaxies/*.tre`** (hors Git si volumineux — à fournir localement). Copie vers la VM **245** :

```bash
# Sur la machine de dev (adapter les chemins)
ssh lbg@192.168.0.245 'sudo install -d -o lbg -g lbg -m 0755 /opt/lbg-new-mmo/tre'

rsync -av --progress -e ssh \
  /chemin/vers/new_mmo/StarWarsGalaxies/*.tre \
  lbg@192.168.0.245:/opt/lbg-new-mmo/tre/
```

Vérifier que **chaque** nom listé dans **`TreFiles`** (dans `conf/config.lua`) existe bien dans ce dossier.

### 4.2 Exemple minimal `config-local.lua` (sur la VM)

Ne **pas** modifier `config.lua` à la main pour le périmètre prod : créer **`MMOCoreORB/bin/conf/config-local.lua`** avec au minimum `TrePath` et les champs DB alignés sur MariaDB. Le `ConfigManager` charge `config.lua` puis applique `config-local.lua` dans le même état Lua (`Core3.*`).

### 4.3 Ancienne note (symptômes)

Sans `.tre` au bon chemin : erreurs `TreeFile`, **`SkillManager`] Could not load skills**, **`PlayerCreationManager`** incomplet ; un correctif code peut éviter un crash ponctuel dans `loadLuaStartingItems`, mais **sans archives complètes le serveur ne sera pas fonctionnel**.

## 5. Lancer le serveur

Toujours depuis **`MMOCoreORB/bin/`** (chemins relatifs vers `conf/`, etc.) :

```bash
cd /opt/lbg-new-mmo/MMOCoreORB/bin
./core3-swgemu
```

Exemple **arrière-plan** avec journal fichier :

```bash
cd /opt/lbg-new-mmo/MMOCoreORB/bin
pkill -x core3-swgemu 2>/dev/null || true
nohup ./core3-swgemu > /tmp/core3-swgemu.log 2>&1 &
tail -f /tmp/core3-swgemu.log
```

### 5.1 Deux instances en parallèle (SWGEmu stock + Core3 « clean » Antigravity)

Sur la **VM 245**, deux serveurs peuvent tourner **simultanément** avec des ports et une galaxie SQL distincts :

| Instance | Nom client (`galaxy.name`) | Répertoire | Binaire | Login / ping / zone (UDP) | `galaxy_id` |
|----------|---------------------------|------------|---------|---------------------------|-------------|
| **SWGEmu stock (Pre-CU)** | **LBG SWGEMU PreCu** | `/opt/lbg-new-mmo/MMOCoreORB` | `bin/core3-swgemu` | 44453 / 44462 / 44463 | 2 |
| **Clean / Antigravity (prod LBG)** | **LBG MMO Serveur Prime** | `/opt/lbg-new-mmo-clean/MMOCoreORB` | `bin/core3-clean` | 44553 / 44562 / 44563 | 3 |

- **`.tre` partagés** : `TrePath` → `/opt/lbg-new-mmo/tre` pour les deux.
- **MariaDB** : même base `swgemu` ; ligne **`galaxy`** id **3** (snippet `infra/snippets/core3-galaxy-clean-lan245.sql`).
- **Berkeley DB locale** (`bin/databases/`) : **séparée** par instance (ne pas rsync les `databases/` de dev vers la prod stock).

**Poste de dev** (depuis `LBG_IA_MMO/`) :

```bash
# Une fois : préparer arborescences + galaxie SQL sur la VM
bash infra/scripts/setup_core3_dual_vm.sh

# Instance clean = build Antigravity (lbg-mmo/server-core3), pas MMOCoreORB seul
bash infra/scripts/build_core3_antigravity_vm.sh --sync
# … attendre la fin du build sur la VM …
bash infra/scripts/install_core3_clean_after_vm_build.sh

# Démarrer / redémarrer les deux (stock + clean)
bash infra/scripts/start_core3_dual_vm.sh
```

Scripts dédiés :

| Script | Rôle |
|--------|------|
| `rsync_lbg_mmo_antigravity_vm.sh` | Sources `lbg-mmo` (MMOEngine + server-core3) → `/opt/lbg-antigravity/lbg-mmo` |
| `build_core3_antigravity_vm.sh` | Compile sur la VM (`--sync` optionnel) ; journal `/tmp/core3-antigravity-build.log` |
| `install_core3_clean_after_vm_build.sh` | Copie le binaire vers `core3-clean` et démarre |
| `rsync_new_mmo_core3_clean.sh` | Ancien sync MMOCoreORB seul (legacy, pas le build Antigravity) |

**Binaire Antigravity local** : `lbg-mmo/build/server-core3/core3` — ne pas le copier tel quel sur la VM (glibc WSL ≠ VM) ; compiler sur la VM.

**Client SWG** : choisir l’IP **192.168.0.245** et le **port login** de l’instance voulue (44453 stock ou 44553 clean) ; la liste des galaxies affiche les deux mondes si les deux login tournent.

## 5 bis. IP vue par le client (login → zone)

Dans ce fork Core3, **`config.lua` ne définit en général pas** `LoginServerAddress` / `ZoneServerAddress`. Après auth, le login envoie **`LoginClusterStatus`** avec l’IP / ports lus depuis la table **`galaxy`** (voir `GalaxyList` / `LoginClusterStatus::addGalaxy`). Si **`galaxy.address`** vaut **`127.0.0.1`**, un client sur une autre machine recevra cette adresse pour joindre la zone → échec.

À corriger sur la VM (exemple LAN **192.168.0.245**, `galaxy_id` aligné sur **`ZoneGalaxyID`** dans `config.lua`, souvent **2**) :

```sql
UPDATE swgemu.galaxy SET address = '192.168.0.245' WHERE galaxy_id = 2;
```

**Nom affiché dans le client (liste des serveurs / galaxie)** : colonne **`galaxy.name`** (ex. remplacer le défaut type **`MtGServer Development`** par le libellé produit) :

```sql
UPDATE swgemu.galaxy SET name = 'LBG SWGEMU PreCu' WHERE galaxy_id = 2;
UPDATE swgemu.galaxy SET name = 'LBG MMO Serveur Prime' WHERE galaxy_id = 3;
```

Recette LAN **VM 245** : **`infra/snippets/core3-galaxy-rename-dual-lan245.sql`** (les deux noms). Par galaxie : id **2** → `core3-galaxy-rename-lan245.sql` ; id **3** → `core3-galaxy-clean-lan245.sql`.

Les colonnes **`port`** / **`pingport`** doivent correspondre aux ports UDP réellement utilisés par `core3` (souvent **zone 44463**, **ping 44462** — vérifier avec `ss -ulnp | grep core3`). L’adresse IP du **serveur login** côté client est en pratique celle saisie dans la config du **client** SWG ; seule l’IP **zone** est poussée par la réponse login ci‑dessus.

**Attention protocole** : login / ping / zone SWGEmu utilisent **UDP**, pas TCP. Une commande du type `netstat -tulpn | grep 44453` ou `ss -ulnp | grep core3` est adaptée ; **`ss -tlnp`** ne montrera en général **pas** ces ports.

## 6. Confirmer que tout s’est bien passé

- **Processus** : `pgrep -a core3`
- **Logs console** : recherche **`[Core] initialized`**, éventuellement **`READY`** ; pour la zone : `grep ZoneServer /tmp/core3.log`
- **Ports UDP Core3** (à ajuster si tu changes `config.lua`) : login **`LoginPort`** (souvent **44453**), ping **`PingPort`** (**44462**), zone **`galaxy.port`** (**44463** typiquement si lu depuis la DB). Vérification :  
  `ssh lbg@192.168.0.245 'ss -ulnp | grep core3'`  
  L’**ORB** (**44419**, TCP) sert au broker interne ; ce n’est pas l’IP que le client SWG classique utilise comme « adresse jeu » dans le launcher.

## 7. Cartographie avec la stack LBG (VM 245)

| Composant              | Rôle                          | Port / note typique        |
|------------------------|-------------------------------|----------------------------|
| `mmmorpg_server`       | WebSocket pont IA ↔ jeu LBG | 7733 / 8773 (voir runbook) |
| `mmo_server`           | Simulation headless Python   | 8050                       |
| **`core3` (SWGEmu)**  | Serveur jeu Pre‑CU distinct  | login 44453, ping 44462, … |

Référence LAN : `docs/fusion_env_lan.md`, validation rapide : `docs/runbook_validation_serveurs_lan.md`.

## 8. Synthèse — derniers points à ne pas oublier

À garder sous la main avant de « couper » une session ou de tester depuis un **poste client sur le LAN** :

| Sujet | Détail |
|--------|--------|
| **IP zone envoyée au client** | Ce n’est **pas** `LoginServerAddress` / `ZoneServerAddress` dans `config.lua` (absents dans ce fork). C’est **`swgemu.galaxy.address`** pour la ligne dont **`galaxy_id` = `ZoneGalaxyID`**. Mettre l’IP **LAN de la VM** (ex. `192.168.0.245`), **pas** `127.0.0.1`. |
| **Nom galaxie (client)** | **`swgemu.galaxy.name`** — id **2** : **LBG SWGEMU PreCu** ; id **3** : **LBG MMO Serveur Prime** (`infra/snippets/core3-galaxy-rename-dual-lan245.sql`). |
| **Ports** | Login / ping / zone en **UDP** (`ss -ulnp`). Vérifier cohérence **`galaxy.port`** / **`galaxy.pingport`** avec ce qu’écoute `core3`. |
| **Client SWG** | Le joueur doit pointer le **login** vers la même IP LAN (fichier options du client / launcher). |
| **MariaDB** | **`DBPass`** (`config` / `config-local.lua`) = mot de passe réel de **`DBUser`** (`ALTER USER …`). |
| **Comptes SQL** | Pas de **`PASSWORD()`** MySQL : Core3 utilise **`SHA256(DBSecret + motdepasse + salt)`** et **`salt`** non vide ; voir correctifs déjà appliqués en ops sur les comptes test. |
| **Patch segfault chargement** | Sans `.tre`, risque de crash dans `PlayerCreationManager::loadLuaStartingItems` ; correctif **code** possible, mais **les `.tre` restent obligatoires** pour un serveur jouable. |
| **`config-local.lua`** | Sur la VM uniquement si tu ne veux pas le versionner : **`TrePath`**, DB ; rsync des sources ne remplace pas ce fichier tant qu’il n’est pas dans l’arborescence poussée. |
| **`rev.txt`** | Optionnel ; évite un warning au boot. |
