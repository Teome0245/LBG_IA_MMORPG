# ADR 0003 — OpenGame comme forge de prototypes orchestrée

## Statut

**Accepté** — 2026-05-01

## Contexte

OpenGame (`leigest519/OpenGame`) est un framework agentique TypeScript orienté génération de jeux web complets à partir d'un prompt. Il apporte des capacités intéressantes pour produire rapidement des prototypes jouables, tester des boucles gameplay, générer des scènes Phaser / canvas / Vite, et explorer des interfaces ou mini-jeux.

Le projet `LBG_IA_MMO` possède déjà une architecture canonique :

- `orchestrator/` décide du routage des intentions et reste le point d'entrée maître des agents.
- `backend/` expose les contrats API et les proxys de pilotage.
- `agents/` exécute des capabilities bornées, observables et testables.
- `mmo_server/` et `mmmorpg_server/` portent l'état monde, le jeu multijoueur et les ponts IA.
- `pilot_web/` et `web_client/` exposent les interfaces utilisateur.

Sans cadrage, intégrer OpenGame directement pourrait créer un second centre de décision agentique, disperser les générations de code, ou contourner les garde-fous déjà mis en place autour des agents, du LAN privé, de l'audit et des approbations.

## Décision

1. **L'orchestrateur reste le maître d'orchestre** : OpenGame ne devient pas un runtime autonome du produit. Toute génération déclenchée depuis `LBG_IA_MMO` doit passer par une capability orchestrée, par exemple `game_generation` ou `prototype_game`.

2. **OpenGame est une forge de prototypes** : son rôle cible est de générer des mini-jeux, scènes, boucles gameplay, maquettes visuelles, ou prototypes de systèmes. Le MMO principal reste autoritatif pour le monde persistant, les PNJ, la réconciliation IA -> jeu, et le gameplay durable.

3. **Intégration via agent dédié** : l'intégration se fera, si elle est implémentée, par un worker borné (`agent.opengame`) appelé après routage par `lbg_agents.dispatch`, sur le même modèle que les autres agents HTTP.

4. **Sandbox obligatoire** : les générations doivent écrire dans un répertoire isolé et configurable, par exemple `generated_games/` ou `sandbox/opengame/`. Aucun fichier du coeur projet (`backend/`, `orchestrator/`, `agents/`, `mmo_server/`, `mmmorpg_server/`, `web_client/`, `pilot_web/`) ne doit être modifié automatiquement par OpenGame.

5. **Exécution contrôlée** : les commandes shell, installations npm, builds et serveurs de preview sont interdits par défaut ou soumis à garde-fous explicites : dry-run, allowlist, quotas, timeout, audit JSONL, et approbation humaine pour toute exécution réelle. Le mode `--yolo` ne doit pas être utilisé hors sandbox contrôlée.

6. **Promotion manuelle vers le MMO** : un prototype généré peut inspirer une feature, mais son intégration au MMO se fait par changement normal dans le monorepo : revue, adaptation aux contrats existants, tests, documentation et déploiement.

## Conséquences

### Positives

- Exploration gameplay rapide sans fragiliser le coeur MMO.
- Alignement avec l'architecture agentique existante : capability, worker, audit, pilotage.
- Possibilité de créer une bibliothèque de prototypes consultables depuis `/pilot/` ou une route dédiée.
- Réduction du risque de dérive : le code généré reste séparé tant qu'il n'est pas repris manuellement.

### Négatives / coûts

- Nécessite Node.js 20+, une gestion des dépendances npm et des clés API éventuelles selon les providers utilisés.
- La génération de jeux est coûteuse et non déterministe ; il faut des quotas, logs et nettoyages.
- Les prototypes générés peuvent être de qualité variable et ne remplacent pas l'intégration gameplay réelle.
- Les contenus sous IP tierce dans les démos OpenGame ne doivent pas être importés tels quels.

### Mesures de suivi

- Ajouter une capability expérimentale uniquement après un spike local hors production.
- Documenter les variables d'environnement (`OPENGAME_*`, dossier sandbox, quotas) avant tout déploiement.
- Exposer les prototypes en lecture seule, avec une séparation claire entre "prototype généré" et "feature intégrée".
- Mettre à jour ce ADR si OpenGame devient une dépendance installée, un sous-module, ou un service permanent.

## Références

- `docs/architecture.md` — composants orchestrateur / agents / frontend.
- `docs/plan_de_route.md` — suivi roadmap et historique.
- `docs/adr/0001-tronc-monorepo.md` — tronc unique `LBG_IA_MMO`.
- `docs/adr/0002-mmo-autorite-pont.md` — autorité monde et pont jeu ↔ IA.
- `https://github.com/leigest519/OpenGame` — source OpenGame.
