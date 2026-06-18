# Dépannage — lbgemu.exe ne démarre plus

## Cause probable (mai 2026)

Le fichier **`patch_lbg_00.tre`** (commande `/lbgwe`) avait un **offset interne incorrect** dans sa première version. Le client SWG peut **quitter immédiatement** au chargement des TRE listés dans `swgemu_live.cfg` / `user.cfg`, sans message visible.

**Correctif publié** : TRE régénéré + manifeste Prime sans écrasement de `lbgemu.exe`.

## Réparation rapide (Windows)

### 1. Mettre à jour via le launchpad

1. LBG Launchpad → profil **Prime**
2. **Vérifier Mises à Jour** (pas seulement « Client à jour »)
3. Attendre le téléchargement de `patch_lbg_00.tre` (nouveau hash)
4. Relancer **JOUER**

### 2. Commenter `user.cfg` ne suffit pas

`swgemu.cfg` charge **`swgemu_live.cfg`**, qui référençait aussi `patch_lbg_00.tre`. Il faut corriger **les deux** (ou lancer le script de récupération).

**Script automatique (PowerShell, recommandé)** :

```powershell
cd \\wsl$\Ubuntu\home\sdesh\projects\LBG_IA_MMORPG\LBG_IA_MMO\infra\scripts
.\recover_prime_client.ps1 -GameDir "J:\swgemu\clients\prime-lbg"
```

Le script : retire `patch_lbg` des cfg, renomme le TRE, restaure `lbgemu.exe` depuis PreCu, teste 5 s.

**Manuel** — dans `clients\prime-lbg\` :

- `user.cfg` : pas de ligne `searchTree_00_25`
- `swgemu_live.cfg` : `maxSearchPriority=25`, pas de `searchTree_00_25`
- Renommer `patch_lbg_00.tre` → `patch_lbg_00.tre.bak`

Puis launchpad → **Vérifier Mises à Jour** (manifeste `prime-recovery-*` sans TRE).

### 3. Restaurer l’exécutable si besoin

Si le launchpad a remplacé un `lbgemu.exe` qui fonctionnait :

```cmd
cd J:\swgemu\clients\prime-lbg
copy /Y ..\precu-original\SWGEmu.exe lbgemu.exe
```

Ou recopier depuis une sauvegarde locale.

Le canal patch **ne pousse plus** `lbgemu.exe` automatiquement (cfg + TRE seulement).

### 4. Lancer en ligne de commande (voir l’erreur)

```cmd
cd J:\swgemu\clients\prime-lbg
lbgemu.exe -s swgemu.cfg
```

Si une fenêtre apparaît puis se ferme, vérifier :

- Antivirus / Windows Defender (quarantaine sur `lbgemu.exe`)
- Fichiers `.tre` manquants (`patch_fr_00.tre`, `data_*.tre`, etc.)
- Espace disque

## Vérifier le patch TRE

Le nouveau `patch_lbg_00.tre` fait ~1,7 Ko et charge une table de commandes valide. Hash MD5 attendu (manifeste Prime sur VM 245) :

```bash
curl -s http://192.168.0.245:8080/patches/prime/manifest.json | grep -A1 patch_lbg
```

## Workaround World Editor sans patch client

Chat **Spatial** (onglet Spatial, sans `/`) :

```text
lbg_we session on
```

## Signaler un blocage

Indiquer :

- Message du launchpad au clic **JOUER**
- Taille de `lbgemu.exe` et date de modification
- Présence de `patch_lbg_00.tre` dans le dossier client
- Résultat de `lbgemu.exe -s swgemu.cfg` en cmd
