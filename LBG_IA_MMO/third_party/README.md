# Répertoire **`third_party/`** — dépendances lourdes hors tronc Python

## Objectif

Accueillir des arbres **volumineux** ou **non Python** (moteurs C++, assets, clones de dépôts externes) **sans** les mélanger au code applicatif versionné du monorepo de façon involontaire.

## **`new_mmo` (Core3 / SWGEmu)**

1. **Option recommandée pour le développement** : garder un clone à côté du monorepo, ex. **`~/projects/new_mmo`** (voir `docs/migration_new_mmo_core3.md`).

2. **Option `third_party/new_mmo`** : cloner ici si vous voulez un chemin **relatif** au monorepo :

   ```bash
   cd LBG_IA_MMO/third_party
   git clone <URL_DU_DEPOT_NEW_MMO> new_mmo
   ```

   Le dossier **`new_mmo/`** est listé dans **`.gitignore`** à la racine de **`LBG_IA_MMO/`** : le contenu du clone **n’est pas commité** dans le dépôt LBG_IA_MMO (évite gigantisme + binaires).

3. **Submodule Git** : si l’équipe choisit un submodule à la place d’un clone ignoré, suivre `docs/migration_new_mmo_core3.md` §3 option C et **retirer** l’ignore correspondant pour ne versionner que le **pointeur** submodule.

## Règles

- Ne **committez pas** de binaires `core3`, dumps SQL complets, ni builds entiers dans le tronc **`LBG_IA_MMO/`** sans revue explicite.
- Toute nouvelle entrée sous **`third_party/`** doit être **mentionnée** dans la doc (ADR ou guide de migration) et, si ignorée, référencée dans **`.gitignore`**.
