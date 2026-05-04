# Vision & synthèse (LBG‑IA)

Ce document formalise la vision issue de `Detail du projet_v3_20260409.txt`.

## Objectif fondamental

**Recentrage (priorité produit)** — formalisé aussi dans `docs/plan_de_route.md` § *Étoile du nord produit*, à partir de `Boite à idées/20260428_1220_on ce recentre.txt` :

1. **D’abord** une **IA incarnée sur le poste et l’infra** : actions concrètes et contrôlées (ex. ouvrir le bloc-notes et écrire à la dictée, ouvrir des pages web, lire des mails pertinent sous **garde-fous** — dry-run, allowlists, audit). Piste : `docs/desktop_hybride.md`, ADR **`docs/adr/0004-assistant-local-vs-persona-mmo.md`**.
2. **Ensuite** une **partie de cette même famille** au **cœur du MMO** : persona / dialogue / apprentissage dans un **contexte simulé**, sans fusionner abusivement les périmètres poste ↔ monde (même ADR).
3. **Enfin** la capacité à **faire évoluer** le MMO et le code : uniquement via **chemins explicites** (forge sandbox, promotions manuelles, pas d’écriture aveugle sur le tronc autoritaire — voir `docs/adr/0003-opengame-forge-prototypes.md`).

---

## Synthèse historique (carnet de bord initial)

Construire **un orchestrateur IA autonome** capable de piloter :
- plusieurs **LLM** (locaux + cloud)
- plusieurs **agents** (Windows, Linux, VM, DevOps)
- un système d’**auto‑évolution** et d’**auto‑maintenance**
- une **IA incarnée** (Lyra)
- un **univers MMO bac à sable** persistant, où cette IA peut vivre, évoluer et interagir

En une phrase : **un cerveau central** qui pense, apprend, agit, se maintient, se corrige et interagit aussi dans un monde virtuel.

## Principe transversal — IA curieuse

La curiosité IA est une **orientation générale du projet**, pas uniquement une mécanique MMO. Elle doit pouvoir s'appliquer :
- **dans le MMORPG** : PNJ, créatures, factions ou agents de simulation capables d'explorer, de réagir aux situations nouvelles, de mémoriser les anomalies utiles et d'adapter leurs routines ;
- **hors MMORPG** : orchestrateur, assistants et agents autonomes capables de détecter la nouveauté, d'estimer leur incertitude, de tester des hypothèses et d'améliorer progressivement leur comportement.

Les signaux envisagés restent conceptuels à ce stade :
- **nouveauté** : valoriser un état, une information ou une situation jamais rencontrée ;
- **erreur de prédiction** : transformer l'écart entre attente et réalité en opportunité d'apprentissage ;
- **exploration contrôlée** : autoriser l'agent à sortir temporairement des routines connues, dans des limites sûres et observables.

Ce principe sert de repère pour les futurs travaux sur les PNJ, la mémoire, l'orchestration, l'autonomie et Lyra. Il ne constitue pas un plan figé ni une obligation d'implémentation immédiate.

## Orchestrateur IA — “le cerveau”

Responsabilités attendues :
- sélection du **bon modèle** (local/API)
- sélection du **bon agent** (Windows/Linux/VM/DevOps)
- sélection de la **capability** (action à exécuter)
- **routage** des tâches, **fallback**, gestion d’erreurs
- capacité à **apprendre** de nouvelles intentions et à étendre ses capacités

## Agents — “les bras et les mains”

Deux familles principales :
- **Agents classiques** : exécution des tâches non sensibles (opérations quotidiennes)
- **Agents DevOps (haut privilège)** : actions sensibles (patch, rebuild, déploiement, logs, gestion VM, auto‑évolution)

Règle d’or : **les agents DevOps ne doivent pas exécuter les tâches basiques** — ils délèguent aux agents classiques.

## Auto‑évolution & auto‑maintenance

Boucle cible :
- détecter un problème
- analyser (code/état/logs)
- proposer/générer un patch
- appliquer via agent DevOps
- rebuild + tests
- rollback si nécessaire

## Lyra — IA incarnée

Lyra influence :
- ton et style de réponse
- patience, créativité
- à terme : **personnage vivant** dans l’univers (pas un PNJ)

Voir aussi `docs/lyra.md`.

## MMO bac à sable / multivers

Piliers :
- univers persistant multi‑planètes (dont une exception “terre‑plate”)
- professions/social/craft/exploration possibles **sans combat**
- PNJ intelligents (routines, objectifs, quêtes “uniques”)
- joueurs humains + joueurs IA

Voir aussi `docs/plan_mmorpg.md`.

## Point de situation technique (monorepo, avril 2026)

Sans remplacer la vision ci‑dessus : le dépôt **`LBG_IA_MMO/`** porte déjà **backend**, **orchestrator**, **agents**, **`mmo_server`**, **`mmmorpg_server`**, déploiement **systemd** / LAN documentés (**`bootstrap.md`**, **`docs/fusion_env_lan.md`**, **`docs/runbook_validation_serveurs_lan.md`**). **Observabilité** : métriques Prometheus **`/metrics`** en opt-in sur les services HTTP concernés.

**Ordre de traction court / moyen terme** (aligné *Étoile du nord*) : renforcer le **desktop hybride** et les parcours **poste/infra** sous audit ; en parallèle, jalons **MMO gameplay** et **pont dialogue** déjà tracés dans **`docs/plan_de_route.md`** (jalon #6, inventaire, etc.) sans sacrifier la **sécurité et la séparation** assistant local / persona MMO.

