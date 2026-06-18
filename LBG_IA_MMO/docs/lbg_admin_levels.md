# Niveaux admin LBG-MMO-Core3 (référence courte)

Grille cible : **ADR [0006-lbg-admin-levels-refonte.md](adr/0006-lbg-admin-levels-refonte.md)**.

## Échelle 0–4

| ID | Nom | Tag | Compte (UI web) | God en jeu |
|----|-----|-----|-----------------|------------|
| 0 | Player | — | Joueur | Non |
| 1 | GM | LBG-GM | Non | Non |
| 2 | Moderator | LBG-Mod | Modération | Non |
| 3 | Dev | LBG-Dev | Debug | Non |
| 4 | Admin | LBG-Admin | Complet (Teome) | **Manuel** uniquement |

**Ordre** : Player < GM < Moderator < Dev < **Admin** (Admin = ancien Owner + Admin SWGEmu fusionnés).

## Règles essentielles

- Nouveau perso : toujours **niveau 0**, pas de god hérité du compte.
- God : seulement pour un perso **Admin (4)** avec activation manuelle (`/setGodMode self on`). Les niveaux 1–3 n’ont pas `admin_base` ; pas de god tant que l’ability `admin` n’est pas activée (phase 2 C++).
- Jedi, spawn lourd, économie globale : palier **Admin (4)**.
- Migration anciens IDs 0–15 → 0–4 : voir ADR 0006 (double lecture 2 semaines).

## Stratégie

**C — Aligné** : mêmes niveaux **0–4** sur **LBG SWGEMU PreCu** et **LBG MMO Serveur Prime** (comptes SQL partagés).

## Teome

- Compte SQL : **4 (Admin)** sur les deux mondes.
- Gameplay normal : perso en **0** ; activer staff/god quand tu modères (`/setGodMode self on`, Prime et PreCu).
