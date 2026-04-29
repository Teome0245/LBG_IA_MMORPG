# Walkthrough : Transition Continentale (Eldoria)

Nous avons transformé le prototype de village en un monde à l'échelle continentale de **5 243 km²**.

## 🚀 Changements Majeurs

### 1. Génération Procédurale
- Intégration du script `world_gen.py` pour produire `planet_map.png`.
- Échelle fixée à **1 pixel = 50 mètres**.
- Dimensions réelles : **102,4 km x 51,2 km**.

### 2. Moteur de Rendu (Web Client)
- **Échelle Monde** : Mise à jour des constantes pour gérer les 102 km de largeur.
- **Système de Zoom** :
    - Amplitude : **0.001** (vue orbitale) à **10.0** (vue rapprochée).
    - Transition fluide via facteur multiplicatif.
- **Entités (LOD)** :
    - Les PNJs et joueurs changent de taille avec le zoom.
    - Les noms des PNJs sont masqués en vue éloignée (< 0.3) pour la lisibilité.

### 3. Serveur & Backend
- **Limites de mouvement** : `BOUNDS_HALF` augmentée de 500m à **60 000m** (60 km).
- **Metadata** : `world_initial.json` mis à jour avec la surface réelle de 5.2 milliards de m².
- **HUD** : Ajout de l'unité **"m"** aux coordonnées X/Y.

## 🛠️ État des Services
- **VM 110 (Front)** : Client web à jour et déployé.
- **VM 245 (MMO)** : Serveur HTTP et WebSocket synchronisés sur la nouvelle échelle.

## 📸 Aperçu de l'Échelle
> [!NOTE]
> Bourg-Palette est situé au centre `(0, 0)`. À l'échelle orbitale (zoom 0.002), le village n'est qu'un point sur l'immense continent d'Eldoria.
