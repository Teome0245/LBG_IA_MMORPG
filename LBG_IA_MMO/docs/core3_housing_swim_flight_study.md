# Étude Prime — Housing, nage, vol atmosphérique

## Contexte

Le serveur **Prime** (`core3-clean`, galaxie 3) repose sur **SWGEmu / Core3**. Les systèmes housing, nage et vol existent en partie dans le moteur vanilla ; l’objectif est d’évaluer ce qui est réutilisable sans refonte client.

## Housing

| Capacité Core3 | Faisabilité Prime | Piste |
|----------------|-------------------|--------|
| Structures / deeds vanilla | Haute | Réutiliser templates `object/building/player/...` |
| Cellules intérieures | Haute | `teleport` + `cell` (déjà utilisé cantina pilotes) |
| Propriété / permissions | Moyenne | Persister via `setQuestStatus` / DB custom |
| Décoration libre | Basse (hors scope MVP) | Phase ultérieure |

**MVP implémenté côté bridge** : commande `housing_enter` (téléport vers coords + cell de test) + persistance clé `ia_bridge:housing:<player>`.

## Nage

| Élément | État |
|---------|------|
| Zones eau (terrain) | Déjà dans navmesh / planet manager |
| Dégâts noyade | Buffs / wounds vanilla |
| Oxygène custom | Nécessite hook C++ ou buff scripté |

**MVP** : règle planète `swim_enabled` dans `core3_planet_rules.json` + message système si zone désactivée.

## Vol atmosphérique

| Élément | État |
|---------|------|
| Véhicules aériens | Templates JTL / speeders — dépend `.tre` |
| Physique altitude | Moteur vanilla |
| Transition espace | JTL optionnel |

**MVP** : pas de vol custom ; documenter dépendance véhicules + anti-exploit (vitesse max serveur).

## Prochaines étapes recommandées

1. POC housing : 1 lot Mos Eisley + deed test + persistance MariaDB.
2. Audit templates véhicules volants disponibles sur Prime.
3. Hook C++ `PlanetRules::canSwim` / `canFly` si règles multivers requises.
