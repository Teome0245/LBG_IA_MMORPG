# Terraformer une zone — créer un plateau (Lost Heaven)

**Prérequis** : Dev+ sur Tatooine, Core3 avec `addTerrainFlatten` + `spawnTheaterObject` (patch LBG déployé).

## Deux couches

| Couche | Outil serveur | Effet |
|--------|---------------|--------|
| **Sol serveur** | `addTerrainFlatten` | Heightmap — collision, spawn, `getPlanetHeight` |
| **Sol client** | `spawnTheaterObject` | Aplatit le mesh visible **sans relog** |

Pour un plateau stable : **toujours les deux** (`terrain plateau`).

## Pourquoi le terrain « revient » ?

Le plat que tu vois peut disparaître pour trois raisons :

1. **Theaters seulement** — sans `terrain/poi_small.lay` sur le serveur, le flatten **serveur** ne s’applique pas (`mods=0` dans `terrain status`). Seuls les theaters aplatissent le mesh **tant qu’ils existent en zone**.
2. **Restart Core3** — theaters et mods terrain sont en **mémoire** (pas en base). Au redémarrage, tout est effacé.
3. **Fichier OID périmé** — `lbg_we_theater_oids.txt` peut lister 1000+ OIDs morts après un restart ; `terrain status` affiche `live=0`.

**Correctifs** :
- `lbg_we terrain plateau` sauvegarde `ia_bridge/lbg_terrain_plateau.json`
- Au boot zone, le serveur **rejoue** le plateau automatiquement (si config présente)
- Manuel : `lbg_we terrain replay`
- Flatten serveur durable : déployer `terrain/poi_small.lay` dans le répertoire `bin/` Core3 (fichier absent des TRE client Prime actuels)

**Génération automatique (repo LBG)** :

```bash
python3 tools/client_patch/generate_poi_lay.py
bash infra/scripts/deploy_terrain_lay_vm.sh
bash infra/scripts/deploy_core3_ia_bridge_vm.sh --restart
```

Produit `poi_small.lay` (16 m), `poi_medium.lay` (32 m), `poi_large.lay` (64 m) — rayons alignés sur les templates POI SOE.

## Workflow étape par étape (IG)

```
lbg_we hub freeze          ← pas de repop auto pendant les tests
lbg_we hub goto            ← ancre Lost Heaven
```

### 1. Choisir le centre

```
lbg_we terrain anchor      ← centre plateau = ta position actuelle
```

### 2. Mesurer le relief

```
lbg_we terrain scan 20 5   ← grille 11×11, pas 20 m → min/max/delta
```

Si **delta > 3 m** → plateau obligatoire avant bâtiments.

### 3. Créer le plateau

```
lbg_we terrain plateau 48 6
```

- **48** = pas entre cellules (m)
- **6** = demi-largeur en cellules → emprise ≈ **48 × 6 × 2 = 576 m**

Variantes :

```
lbg_we terrain plateau here 50 8    ← centre = pieds, pas 50 m, half 8
lbg_we terrain flatten grid 48 6    ← serveur seulement (relog pour voir)
lbg_we terrain theater 48 6         ← client seulement (visible tout de suite)
```

### 4. Vérifier

```
lbg_we terrain status
lbg_we terrain replay          ← après restart si le plat a disparu
lbg_we terrain height
lbg_we dump json
```

Marcher sur le plateau — **relog** si le sol serveur semble inchangé (theaters = immédiat).

### 5. Effacer et recommencer

```
lbg_we terrain clear           ← mods WE seulement
lbg_we terrain clear all       ← WE + Lost Heaven
```

## Paramètres Lost Heaven (screenplay)

| Param | Valeur |
|-------|--------|
| Ancre | 4749, -737 |
| Pas | 50 m |
| Half | 9 cellules (~900 m) |

Hub dédié : `lbg_we hub terrain` (même moteur, ancre fixe hub).

## Fichiers

| Fichier | Rôle |
|---------|------|
| `lbg_terrain_lib.lua` | Moteur plateau partagé |
| `ia_bridge/lbg_we_terrain_mod_ids.txt` | IDs flatten serveur |
| `ia_bridge/lbg_we_theater_oids.txt` | OIDs theaters client |
| `ia_bridge/lbg_terrain_plateau.json` | Config plateau (replay au boot) |

## Suite

Une fois le plateau OK → placement bâtiments (`lbg_we poi preset` ou Utinni/JTB demain).

Voir aussi : [`docs/adr/0010-lost-heaven-terrain-first.md`](adr/0010-lost-heaven-terrain-first.md)
