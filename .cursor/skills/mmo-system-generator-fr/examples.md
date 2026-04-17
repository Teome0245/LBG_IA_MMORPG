# Exemples d’utilisation — mmo-system-generator-fr

## Exemple 1 — Système météo (data-driven)

**Demande utilisateur**

Génère un système météo data-driven pour `mmo_server/world/weather` : biomes, saisons, transitions, et événements (pluie, neige, tempête). Je veux des tests et une doc.

**Réponse attendue (structure)**

1) Plan (obligatoire)
- But + périmètre MVP
- Données (biomes, saisons, tables de transition)
- Events (weather.changed, storm.started, etc.)
- Interactions (impact sur visibilité, déplacement — si dans MVP)
- Arborescence
- Tests (déterminisme avec seed; transitions limites)
- Docs (README + exemples de configs)

2) Génération
- `data/` (configs)
- moteur (transitions pilotées par data)
- adapters (hook simulation loop)
- tests
- README

## Exemple 2 — Système économie (marché + prix dynamiques)

**Demande utilisateur**

Ajoute un système économie : items, marchés par ville, taxes, et ajustement de prix selon offre/demande. Tout doit être data-driven.

**Réponse attendue (structure)**

1) Plan (obligatoire)
- MVP (prix + stock + transactions)
- Données (items, villes, taxes, elasticité)
- Events (trade.executed, market.repriced)
- Interactions (crafting/loot -> stock; quêtes -> demande)
- Tests (prix bornés, invariants)

2) Génération
- configs + schémas
- moteur de pricing (pur)
- intégration (entity/world)
- tests + README

## Exemple 3 — Système quêtes (génération data-driven)

**Demande utilisateur**

Crée un “Quest Engine” modulaire qui génère des quêtes à partir de templates data-driven et d’events du monde.

**Réponse attendue (structure)**

1) Plan (obligatoire)
- Templates (objectifs, contraintes, récompenses)
- Events d’entrée (npc.met, item.collected, area.entered)
- Interactions (chaînage, échec, cooldown)
- Tests (génération déterministe; validation templates invalides)

2) Génération
- `data/templates/`
- moteur de génération
- bus d’events + handlers
- tests + doc

