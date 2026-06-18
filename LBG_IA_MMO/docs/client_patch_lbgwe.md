# Patch client Prime — commande `/lbgwe`

Le serveur Core3 enregistre déjà `/lbgwe` (`LbgWeCommand.h`), mais le **client SWG** rejette la commande tant qu’elle n’est pas dans `client_command_table.iff` :

> No such command, mood, chat type: lbgwe

Ce patch ajoute `lbgwe` côté client via un TRE dédié **`patch_lbg_00.tre`**.

## Contenu

| Fichier TRE | Rôle |
|-------------|------|
| `datatables/command/client_command_table.iff` | Entrée `lbgwe` (modèle `dumpPausedCommands`) |

## Priorité de chargement

Dans `swgemu_live.cfg` / `user.cfg` (canal **prime** uniquement) :

```ini
[SharedFile]
maxSearchPriority=26
searchTree_00_25=patch_lbg_00.tre
searchTree_00_24=patch_fr_00.tre
```

`patch_lbg_00.tre` (priorité 25) surcharge la table vanilla avant `patch_fr_00.tre` (24).

## Génération (dev)

```bash
cd LBG_IA_MMO
bash tools/client_patch/build_lbgwe_client_patch.sh
```

Sources IFF (par ordre) :

1. `$SWG_ROOT/clients/prime-lbg/datatables/command/client_command_table.iff`
2. `$SWG_ROOT/StarWarsGalaxies/...`
3. `new_mmo/modding_tools/patch_fr_workspace/orig_extracted/...` (dépôt)

Sorties :

- `infra/client-patch-server/patches/prime/patch_lbg_00.tre`
- `client-prime-lbg/patch_build/datatables/command/client_command_table.iff`
- `infra/client-patch-server/patches/prime/patch_lbg_00.json` (métadonnées)

Alternative Windows (SIE) : voir `client-prime-lbg/README_patch_lbg.md`.

## Déploiement joueur

### Via launchpad / patch HTTP (recommandé)

```bash
bash infra/scripts/install_client_patch_server_245.sh
```

Puis dans le client **prime-lbg** : bouton « Vérifier les patches » du LBG Launchpad, ou relancer le launchpad.

### Manuel

Copier dans `clients/prime-lbg/` :

- `patch_lbg_00.tre`
- `swgemu_live.cfg` / `user.cfg` mis à jour (lignes `searchTree_00_25`)

Hard restart du client.

## Test in-game

1. Client **Prime** (`lbgemu.exe`), pas PreCu.
2. Connecter un perso **Dev+** (admin ≥ 3).
3. Taper : `/lbgwe session on`
4. Attendu :
   - `[WorldEditor] commande recue: session on` (C++)
   - puis `[WorldEditor] Session ON (Teome)` (Lua, ~500 ms)

Commandes utiles :

```text
/lbgwe session on
/lbgwe dump
/lbgwe status
/lbgwe npc place npc:core3_brawler_trainer_c
/lbgwe export
```

## Workaround sans patch

Chat **Spatial** (onglet Spatial, sans `/`) :

```text
lbg_we session on
```

Voir `docs/world_editor_plan.md`.

## Scripts

| Script | Rôle |
|--------|------|
| `tools/client_patch/build_lbgwe_client_patch.sh` | Regénère TRE + IFF |
| `tools/client_patch/build_lbgwe_client_patch.py` | Logique patch |
| `infra/scripts/generate_client_patch_manifests.sh` | Manifest MD5 canal prime |
| `infra/scripts/install_client_patch_server_245.sh` | rsync → VM :8080 |

## Hors scope

- Patch PreCu (`SWGEmu.exe`) — World Editor = Prime uniquement.
- Entrée `ui_command.stf` (libellé aide) — optionnel, non requis pour le forward serveur.
