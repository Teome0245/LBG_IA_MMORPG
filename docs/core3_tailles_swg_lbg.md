# Matrice tailles — espèces SWG (serveur actif) vs races LBG

Référence machine : `LBG_IA_MMO/content/core3/core3_species_size_matrix.json` (schema **v3**)

Formule : **taille ≈ base_m × scale**

## Tableau serveur (scales LBG déployés)

| Race / Genre | Base (m) | Scale min | Scale max | Taille min | Taille max |
|--------------|----------|-----------|-----------|------------|------------|
| Bothan F | 1,55 | 0,35 | 0,61 | 0,55 m | 0,95 m |
| Bothan M | 1,65 | 0,36 | 0,61 | 0,60 m | 1,00 m |
| Human F | 1,65 | 0,83 | 1,08 | 1,37 m | 1,78 m |
| Human M | 1,80 | 0,89 | 1,11 | 1,60 m | 2,00 m |
| Ithorian F | 1,90 | 0,89 | 1,03 | 1,69 m | 1,96 m |
| Ithorian M | 2,00 | 0,92 | **1,10** | 1,84 m | **2,20 m** |
| Mon Cal F | 1,70 | 0,86 | **1,06** | 1,46 m | **1,80 m** |
| Mon Cal M | 1,80 | 0,89 | **1,17** | 1,60 m | **2,10 m** |
| Rodian F | 1,65 | **0,21** | **0,48** | **0,35 m** | **0,80 m** |
| Rodian M | 1,75 | **0,23** | **0,51** | **0,40 m** | **0,90 m** |
| Sullustan F | 1,50 | 0,89 | 1,03 | 1,34 m | 1,55 m |
| Sullustan M | 1,60 | 0,92 | 1,06 | 1,47 m | 1,70 m |
| Trandoshan F | 1,80 | 1,00 | 1,22 | 1,80 m | 2,20 m |
| Trandoshan M | 1,90 | 1,03 | 1,25 | 1,96 m | 2,38 m |
| Twi'lek F | 1,75 | **0,23** | 1,08 | **0,40 m** | 1,89 m |
| Twi'lek M | 1,85 | **0,27** | 1,11 | **0,50 m** | 2,05 m |
| Wookiee F | 2,00 | 1,08 | **1,38** | 2,16 m | **2,75 m** |
| Wookiee M | 2,10 | 1,11 | **1,43** | 2,33 m | **3,00 m** |
| Zabrak F | 1,65 | 0,89 | 1,03 | 1,47 m | 1,70 m |
| Zabrak M | 1,75 | 0,92 | 1,06 | 1,61 m | 1,86 m |

**Modifié vs SWG vanilla :** Bothan, Rodian, Twi'lek (min), Mon Cal (max), Ithorian ♂ (max), Wookiee (max).

## Catégories SWG (plages actives, tous genres)

| Tier | Hauteur min–max | Espèces |
|------|-----------------|---------|
| **XS** | 0,35 – 0,90 m | **Rodian** |
| **S** | 0,55 – 1,00 m | **Bothan** |
| **S_M** | 1,34 – 1,70 m | Sullustan |
| **M** | 1,37 – 2,00 m | Humain, Zabrak |
| **M_flex** | 0,40 – 2,05 m | **Twi'lek** (slot le plus polyvalent) |
| **M_L** | 1,46 – 2,10 m | **Mon Cal** |
| **L** | 1,69 – 2,38 m | Ithorian, Trandoshan |
| **XL** | 2,16 – **3,00 m** | **Wookiee** |

## Catégories LBG (lore, cm)

| Code | Plage lore | Races roster 10 |
|------|------------|-----------------|
| XS | 0–40 | Pykrels, K'Miri, Plimps, Tinklings, Fae-Lumes |
| S | 40–90 | Murriks, Mogruls (bas) |
| M | 90–170 | Mogruls (haut), Fel'Ranis |
| L | 170–220 | Mechari, Varkoons |

## Recommandation mapping LBG → slot SWG (avec scales actuels)

| Race LBG | Lore (cm) | Slot SWG recommandé | Taille in-game cible |
|----------|-----------|---------------------|----------------------|
| Pykrels | 20–30 | **Rodian** (min scale) | 0,35–0,45 m |
| K'Miri | 25–40 | **Rodian** / Bothan | 0,35–0,60 m |
| Plimps | 25–35 | **Rodian** | 0,35–0,50 m |
| Tinklings | 30–50 | **Bothan** / Rodian haut | 0,55–0,90 m |
| Fae-Lumes | 35–45 | **Bothan** / **Twi'lek** (bas) | 0,40–0,60 m |
| Murriks | 40–60 | **Bothan** | 0,55–1,00 m |
| Mogruls | 90–120 | **Twi'lek** (bas) / Sullustan | 0,50–1,20 m |
| Fel'Ranis | 140–180 | **Humain** / Twi'lek (haut) | 1,40–1,80 m |
| Mechari | 160–190 | **Mon Cal** / Ithorian | 1,60–2,10 m |
| Varkoons | 150–190 | **Wookiee** (bas–milieu) | 2,15–2,50 m |

## Mapping création PC actuel (`Races.h` / `getSpeciesName`)

À réaligner si besoin avec les slots ci-dessus (ex. Plimps → **Rodian** plutôt que Zabrak maintenant que Rodian accepte 0,35 m).

## Historique

- **v2** : table origine + cible Bothan seulement  
- **v3** : table serveur active complète (ce document)
