# C.2 — Sidecar + catalogue `core3_npc_catalog.json`

**Statut** : implémenté (2026-05-23).

## Comportement

1. Si `CORE3_IA_NPC_CATALOG_JSON` (défaut : `content/core3/core3_npc_catalog.json`) existe avec `schema_version >= 2` et des `entries` **active** → source **`catalog`**.
2. Sinon repli sur `core3_npc_pilots.json` (**legacy**).
3. `POST /v1/npc-think` injecte le `system_hint` et `max_tokens` du profil catalogue.
4. `actions_allowed` du profil filtre les actions (`npc_say`, `noop`).
5. `GET /v1/npc-pilots` expose `profile_id` + `llm_system_hint` (sans `_profile` interne).

## Variables

| Variable | Défaut |
|----------|--------|
| `CORE3_IA_NPC_CATALOG_JSON` | `/opt/LBG_IA_MMO/content/core3/core3_npc_catalog.json` |

## Smoke

```bash
bash infra/scripts/smoke_core3_ia_phase_c2_catalog_lan.sh --with-think
```

(`healthz` doit afficher `phase: C2`, `registry_source: catalog`).

## Déploiement VM 245

```bash
bash infra/scripts/configure_core3_ia_llm_vm.sh auto
# ou deploy_core3_ia_bridge_vm.sh (copie catalogue + sidecar)
```

## Suite

**C.3** — premier remplacement PNJ vanilla (`vanilla_replacements`).
