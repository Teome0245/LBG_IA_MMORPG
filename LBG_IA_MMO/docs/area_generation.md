# Génération de Zones Locales (Grilles 2D)

### Échelle du Monde
- **Continent** : 1px = 50m (Planète).
- **Zones Locales** : 1 tuile = 2m.
- **Rendu Client** : 8px = 1m (Échelle humaine). Les personnages sont scalés à ~0.6m de large.

Ce document décrit le fonctionnement des générateurs de zones locales intégrés dans `mmo_server/world/tools/area_gen.py`. Ces outils permettent de créer des structures détaillées (villes, villages, donjons) à intégrer dans le continent.

## 🧱 Modèle de Données : La Grille
Toutes les zones sont représentées par une grille 2D de caractères (Tuiles).

| Symbole | Signification |
| :--- | :--- |
| `.` | Sol / Herbe (Explorable) |
| `#` | Mur / Falaise / Obstacle infranchissable |
| `T` | Arbre |
| `W` | Eau / Marais |
| `H` | Maison / Bâtiment (Défini comme un bloc de 4x4 tuiles dans le rendu Premium pour un total de 64m²) |
| `R` | Route / Chemin (Rendu avec des pavés et des bordures dans la version Premium) |
| `G` | Portail / Entrée de donjon |
| `X` | Ruine / Débris / Puits |

## 🛠️ Générateurs Disponibles

### 1. Ville (`generate_city`)
Génère une ville fortifiée avec :
- Une enceinte de murs (`#`).
- Des routes principales en croix (`R`).
- Quatre quartiers résidentiels avec densité variable de maisons (`H`).
- Une place centrale et une porte d'entrée.

### 2. Village (`generate_village`)
Un village plus organique :
- Un chemin principal traversant.
- Des maisons éparpillées le long du chemin.
- Un point d'intérêt central (Puits/Place).
- Des arbres environnants.

### 3. Zones Locales (`generate_zone_*`)
- **Forêt** : Densité d'arbres élevée avec quelques clairières.
- **Marais** : Mélange d'eau, de boue et d'arbres.
- **Ruines** : Structures rectangulaires brisées avec des débris.

### 4. Donjon Extérieur (`generate_outdoor_dungeon`)
- Une zone de falaise.
- Une entrée de donjon (`G`) au pied de la montagne.
- Un chemin sinueux menant à l'entrée.

## 🔌 Intégration
Ces grilles peuvent être utilisées de deux manières :
1. **Headless Server** : Pour définir les collisions et les points d'apparition des PNJs.
2. **Client 2D** : Pour dessiner des tuiles graphiques correspondantes (Tilesets).

## 🎨 Rendu “carte illustrée” (outil de visualisation)

Le script `mmo_server/world/tools/village_visualizer.py` permet de rendre une grille de village en image.

**Source de la grille (défaut)** : si le fichier `Boite à idées/pixie_seat.json` existe à la racine du dépôt `LBG_IA_MMORPG`, il est chargé comme **village Watabou** (via `watabou_import`). Sinon, retour au village **procédural** 50×40. Pour forcer le procédural : `--procedural`. Pour un autre export Watabou : `--watabou-json /chemin/vers.json`. Les grandes grilles réduisent automatiquement `TILE_SIZE` (plafond `--max-image-px`, défaut 1680).

Deux styles sont disponibles :

- **`premium`** : rendu simple et lisible (utile pour calage, debug, collision/positions).
- **`illustrated`** : rendu plus “peint” (routes organiques, textures, ombres douces) — objectif : se rapprocher d’un fond type “JPG illustré”.

Exemples :

```bash
cd LBG_IA_MMO/mmo_server/world/tools
python3 village_visualizer.py --style premium --seed 42 --out bourg_palette_map.png
python3 village_visualizer.py --style illustrated --seed 42 --out bourg_illustrated.png
# Village procédural historique (sans Watabou) :
python3 village_visualizer.py --style premium --seed 42 --out bourg_palette_map.png --procedural
```

Note : ce script dépend de **Pillow** (`PIL`). Si ton `python3` système ne l’a pas, utilise un venv (ex. `.venv-img/bin/python`) ou installe Pillow dans un environnement dédié.

### Export d'échelle / alignement (meta JSON)

Pour verrouiller l'échelle et éviter les dérives lors d'un changement “artistique”, le visualiseur exporte un fichier meta :

- `--meta-out <fichier>` optionnel
- sinon `<out>.meta.json` par défaut

Ce meta contient :
- `tile_m` (mètres par tuile), `tile_px` (pixels par tuile) et `px_per_m`
- dimensions grille, dimensions image
- convention d'origine (centre image = monde \(0,0\))
- mapping `world(m) -> image(px)`

### Export “plan de masse” + masques (pour Stable Diffusion / ControlNet)

Le visualiseur peut aussi exporter :
- un `layout.json` (objets en coordonnées **monde (m)**)
- un dossier `masks/` (PNG) : `roads.png`, `buildings.png`, `trees.png`

Exemple :

```bash
python3 village_visualizer.py --style illustrated --seed 42 --out bourg_illustrated.png \
  --layout-out bourg_illustrated.layout.json \
  --masks-dir bourg_illustrated.masks
```

Usage recommandé : ComfyUI/A1111 en **img2img** + ControlNet branché sur ces masques, pour obtenir un rendu “peint” tout en respectant strictement positions/échelle.

## Import Watabou (Village Generator) → “premier monde”

Watabou peut exporter une géométrie structurée (JSON) et un rendu (PNG/SVG). Pour **construire le monde serveur** (collisions, obstacles, routes, POI), on préfère importer la **géométrie** plutôt que de “deviner” depuis un PNG.

### Export Watabou

- Export JSON (FeatureCollection) : contient typiquement `earth`, `buildings` (MultiPolygon), `roads` (LineString + width), `trees` (MultiPoint), `fields`, etc.
- Export SVG/PNG : utile pour l’habillage / minimap, mais pas comme source de vérité.

### Outil d’import (grille + layout)

Un importeur minimal est fourni :

- `mmo_server/world/tools/watabou_import.py`

Il génère :
- une **grille ASCII** (`.` `H` `R` `T`) utile pour collisions/debug,
- un **layout JSON** avec polygones bâtiments, polylines routes (avec largeur), positions d’arbres.

Exemple (depuis le repo) :

```bash
cd LBG_IA_MMO/mmo_server/world/tools
python3 watabou_import.py --in "../../../../Boite à idées/pixie_seat.json" --out-dir "/tmp/watabou_pixie" --name "pixie_seat"
ls -la /tmp/watabou_pixie
```

Stats (échelle / surfaces bâtiments vs référence doc 64 m², emprise earth, routes, arbres) :

```bash
cd LBG_IA_MMO/mmo_server/world/tools
python3 watabou_import.py --in "../../../../Boite à idées/pixie_seat.json" --stats-only
# ou en plus de l'export :
python3 watabou_import.py --in "../../../../Boite à idées/pixie_seat.json" --out-dir "/tmp/watabou_pixie" --name "pixie_seat" --stats
# JSON machine :
python3 watabou_import.py --in "../../../../Boite à idées/pixie_seat.json" --stats-only --stats-json "/tmp/pixie_seat.stats.json"
```

Notes :
- `--unit-m` permet d’ajuster la conversion **unités Watabou → mètres** (par défaut 1 unité = 1m).
- `--tile-m` ajuste la résolution de la grille collisions.

## Intégration `mmo_server` (collisions au boot)

Le serveur charge `world/seed_data/pixie_seat.grid.json` (ou le chemin `LBG_MMO_VILLAGE_GRID_JSON`) au démarrage et expose :

- `GET /v1/world/collision` — méta (taille tuile, bounds, etc.), sans token ;
- `GET /internal/v1/world/collision-probe?x=&z=` — tuile et `walkable` (`.` et `R` franchissables ; `H`, `T`, etc. bloqués) ; `X-LBG-Service-Token` si `LBG_MMO_INTERNAL_TOKEN` est défini.
- `GET /v1/world/collision-grid` — export JSON **`watabou_grid_v1`** complet pour le **client** (prédiction de mouvement alignée sur l’autorité). Pour le navigateur, activer **`LBG_MMO_CORS_ORIGINS`** sur le `mmo_server` (voir `mmo_server/README.md`).

### Serveur WebSocket `mmmorpg_server`

Les déplacements côté autorité WS utilisent la même convention (`.` / `R` franchissables). Chargement du JSON `watabou_grid_v1` via `MMMORPG_VILLAGE_GRID_JSON`, puis `LBG_MMO_VILLAGE_GRID_JSON`, puis le même fichier seed `pixie_seat.grid.json` que `mmo_server` si les variables ne pointent pas vers un autre fichier. Si le point monde `(0, 0)` n’est pas sur une tuile franchissable, le **spawn joueur** utilise la première tuile franchissable trouvée en **spirale** depuis la tuile sous `(0, 0)` (centre de tuile en coordonnées monde). Les **PNJ** issus du seed sont recalés sur la tuile franchissable la plus proche si une grille est active. Le **client web** (`web_client`) peut charger la même grille via `GET /v1/world/collision-grid` sur le `mmo_server` (CORS `LBG_MMO_CORS_ORIGINS`) pour une prédiction de mouvement locale alignée. Voir `mmmorpg_server/README.md` (section collisions village).
