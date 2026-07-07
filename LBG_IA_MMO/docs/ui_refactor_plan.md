# Plan refonte UI — pilot_shell (type Cursor)

Document de cadrage **Phase 0** : vision, mapping des vues, stack et déploiement parallèle.

## Objectif

Remplacer progressivement `pilot_web/index.html` (~8 500 lignes monolithiques) par une application **`pilot_shell`** (React + TypeScript) offrant une expérience proche de **Cursor** tout en conservant **100 %** des capacités métier branchées sur `/v1/pilot/*`.

## Correction infra MMO

| Ancien (gelé) | Actuel |
|---------------|--------|
| `mmmorpg_server` WebSocket `:7733` | **Décommissionné** (ADR 0012) — **Core3 Prime VM 246** |

Le client navigateur `web_client` et les proxies pilot restent valides via le backend ; la référence opérateur pour le monde jeu est **Core3 246 Prime**, pas le bac à sable Python.

## Stack retenue

| Couche | Choix | ADR |
|--------|-------|-----|
| Framework UI | React 18 + TypeScript | `docs/adr/0011-pilot-shell-react.md` |
| Build | Vite 5 | — |
| Routage | Hash (`#/…`) — compatibilité StaticFiles | — |
| Style | CSS variables (thème sombre « aurore ») | — |
| État | React context + hooks | Zustand en Phase 2 si besoin |
| API | `pilotApi.ts` (porté P03, étendu tokens legacy) | — |

## Layout cible (coquille IDE)

```
┌──┬────────────┬──────────────────────────────┬──────────────┐
│A │  Sidebar   │     Zone principale          │ Panneau      │
│c │  (nav +    │     (onglet / vue active)    │ Agent        │
│t │   outils)  │                              │ (chat Lyra)  │
│i │            ├──────────────────────────────┴──────────────┤
│v │            │  Panneau bas : Terminal / Logs / Métriques │
│i │            │                                            │
│t │            │                                            │
│y │            │                                            │
└──┴────────────┴────────────────────────────────────────────┘
```

- **Barre d'activité** : icônes Home, Ops, MMO, Jobs, PM, Lyra, Desktop, Santé
- **Sidebar** : navigation secondaire, statut stack, raccourcis
- **Panneau Agent** (droite) : chat orchestrateur — toujours accessible (Phase 2)
- **Panneau bas** : terminal placeholder, logs, métriques (Phase 5)
- **Palette** : `Ctrl+Shift+P` — navigation + actions rapides

## Mapping routes legacy → pilot_shell

| Route legacy (`pilot_web`) | Route v2 (`pilot_shell`) | Phase migration |
|----------------------------|--------------------------|-----------------|
| `#/` | `#/` | Phase 2 (chat home) |
| `#/ops` | `#/ops` | Phase 3 |
| `#/ops/mmo` | `#/mmo` | Phase 3 |
| `#/health` | `#/health` | Phase 3 |
| `#/jobs` | `#/jobs` | Phase 3 |
| `#/pm` | `#/pm` | Phase 3 |
| `#/lyra` | `#/lyra` | Phase 3 |
| `#/desktop` | `#/desktop` | Phase 3 |

Redirections legacy conservées dans l'ancien `index.html` jusqu'à bascule Phase 6.

## Clés localStorage à migrer

| Clé | Usage |
|-----|-------|
| `lbg_pilot_service_token_v1` | Header `X-LBG-Service-Token` |
| `lbg_pilot_token` / `lbg_devops_approval` | Auth P03 (Bearer / approbation) |
| `lbg_pilot_dry_run` | Dry-run DevOps / desktop |
| `lbg_pilot_agentic_chat` | Mode agentique GIR |
| `lbg_pilot_panel_layout_v1` | Layout dashboard drag-and-drop |
| `lbg_pilot_api_base` | URL backend custom |
| `lbg_pilot_chat_state_v1` | État chat home |
| `lbg_pilot_history_v1:*` | Historique PNJ |
| `lbg_pilot_assistant_*` | Assistant Core |
| `lbg_pilot_lyra_*` | Lyra standalone |
| `lbg_pilot_mmo_session_summary_json` | Pont MMO → assistant |
| `lbg_pilot_desktop_*` | Desktop hybride |
| `lbg_pilot_shell_layout_v1` | **Nouveau** — layout coquille IDE |

Couche `src/lib/storage.ts` : lecture des clés legacy sans écrasement.

## Déploiement parallèle

| URL | Contenu |
|-----|---------|
| `/pilot/` | **Redirige vers** `/pilot/v2/` (opt-out : `?legacy=1` ou `localStorage lbg_pilot_legacy_ui=1`) |
| `/pilot/v2/` | Build `pilot_shell` → `pilot_web/v2/` |

```bash
cd LBG_IA_MMO/pilot_shell
npm install
npm run build
# ou : bash infra/scripts/deploy_pilot_shell.sh
```

Backend FastAPI sert déjà `pilot_web/` sous `/pilot` — le sous-dossier `v2/` est exposé automatiquement.

## Phases (rappel)

| Phase | Contenu | Statut |
|-------|---------|--------|
| 0 | Ce document + ADR 0011 | **Terminé** |
| 1 | Coquille IDE + placeholders | **Terminé** |
| 2 | Panneau Agent + chat home | **Terminé** |
| 3 | Vues métier (ops, mmo, jobs…) | **Terminé** |
| 4 | Intégration MMO iframe + companion | **Terminé** |
| 5 | Monaco, xterm, streaming | **Terminé** |
| 6 | Bascule `/pilot/` → v2 | **Terminé** |

## Références réutilisables

- `LBG_Project_03/pilot_web/app/src/lib/pilotApi.ts`
- `LBG_IA/orchestrateur/frontend/src/components/` (Sidebar, ChatFlow, LyraWidget)
- `companion_bot/web/src/ui/App.tsx` (poll events)
- `backend/api/v1/routes/pilot.py` (contrat API stable)
