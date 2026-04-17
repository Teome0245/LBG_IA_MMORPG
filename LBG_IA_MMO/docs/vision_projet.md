# Vision & synthèse (LBG‑IA)

Ce document formalise la vision issue de `Detail du projet_v3_20260409.txt`.

## Objectif fondamental

Construire **un orchestrateur IA autonome** capable de piloter :
- plusieurs **LLM** (locaux + cloud)
- plusieurs **agents** (Windows, Linux, VM, DevOps)
- un système d’**auto‑évolution** et d’**auto‑maintenance**
- une **IA incarnée** (Lyra)
- un **univers MMO bac à sable** persistant, où cette IA peut vivre, évoluer et interagir

En une phrase : **un cerveau central** qui pense, apprend, agit, se maintient, se corrige et interagit dans un monde virtuel.

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

