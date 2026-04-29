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
