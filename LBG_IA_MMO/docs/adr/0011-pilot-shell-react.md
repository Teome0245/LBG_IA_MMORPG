# ADR 0011 — pilot_shell : nouvelle UI React type Cursor

## Statut

Accepté — 2026-07-06

## Contexte

L'UI opérateur `pilot_web/index.html` (~8 500 lignes monolithiques) couvre toutes les capacités pilot (`/v1/pilot/*`) mais est difficile à maintenir et à faire évoluer vers une expérience unifiée type IDE (layout Cursor, panneau agent permanent, palette de commandes).

Des prototypes existent en parallèle : Vue (`LBG_IA/orchestrateur/frontend`), React P03 (`LBG_Project_03/pilot_web`), companion React.

## Décision

1. Créer **`LBG_IA_MMO/pilot_shell/`** — application React 18 + TypeScript + Vite.
2. Déployer en **parallèle** sous `/pilot/v2/` sans casser `/pilot/` legacy.
3. Conserver le **backend inchangé** en phases 0–3 : contrat `/v1/pilot/*` stable.
4. Référence MMO jeu : **Core3 Prime VM 246** — `mmmorpg_server :7733` **décommissionné** (ADR 0012).
5. Routage **hash** (`#/…`) pour compatibilité StaticFiles FastAPI sans rewrite SPA.
6. Migration **incrémentale** par feature (Phases 2–3) ; bascule `/pilot/` en Phase 6.

## Alternatives considérées

| Option | Rejet / report |
|--------|----------------|
| Vue 3 (LBG_IA) | Composants réutilisables mais 2 stacks React déjà en place (companion, P03) |
| Refactor inline `index.html` | Coût élevé, pas de composants, dette maintenue |
| Electron natif dès Phase 1 | Report Phase 6 optionnelle |
| Next.js | Surdimensionné pour SPA statique servie par FastAPI |

## Conséquences

- Nouveau dossier `pilot_shell/` + build artefact dans `pilot_web/v2/`.
- Documentation : `docs/ui_refactor_plan.md`, mise à jour `plan_de_route.md` Historique.
- Tests manuels runbook LAN inchangés ; smoke sur `/pilot/v2/` en complément.
