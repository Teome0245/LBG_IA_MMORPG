# C.3 — Premier remplacement PNJ simple (Kisreudi Teste)

**Cible IG** : scientifique **Kisreudi Teste** Mos Eisley (~3551, 5, -4725).

## Stratégie

| Aspect | Choix |
|--------|--------|
| Type | PNJ **simple** — poste **fixe**, pas de routine quête |
| Mobile Core3 | `scientist` |
| Pont | `npc:core3_kisreudi` ↔ `npc:scientist_mos` (LBG) |
| Suivi Lia | **Non** (`follow_lia: false`) — reste sur place |
| Vanilla | Pas de ligne screenplay trouvée → **replace_spawn** LBG ; despawn GM du doublon manuel si besoin |

## Fichiers

- `content/core3/core3_npc_catalog.json` — `profile:scientist_mos_v1`, entry active
- `content/core3/lua/ia_bridge_screenplay.lua` — spawn fixe
- `agents/src/lbg_agents/npc_registry.json` — `npc:scientist_mos`

## Smoke

```bash
bash infra/scripts/smoke_core3_ia_phase_c3_kisreudi_lan.sh
```

Après redémarrage `core3-clean` : **3** pilotes actifs côté sidecar ; en jeu, **supprimer** l’ancien Kisreudi non piloté si deux modèles se chevauchent.

## Test think

```bash
curl -sS -X POST http://127.0.0.1:8791/v1/npc-think \
  -H 'Content-Type: application/json' \
  -d '{"npc_id":"npc:scientist_mos","prompt":"Presente-toi en une phrase."}'
```

## Test Bige Coto (instructeur Entertainer)

| Champ | Valeur |
|-------|--------|
| Pilote | `npc:core3_bige_coto` |
| LBG | `npc:entertainer_trainer_mos` |
| Mobile | `trainer_entertainer` |
| Poste | ~3477.89, 5, -4791.6 (heading 215) |
| Vanilla | `screenplays/cities/tatooine_mos_eisley.lua` ligne `trainer_entertainer` |

```bash
bash infra/scripts/smoke_core3_ia_phase_c3_bige_lan.sh
```

En jeu : **despawn GM** le trainer vanilla si deux Bige Coto se chevauchent.

## Encodage spatial chat

Les `` dans le chat IG viennent souvent des **accents** / UTF-8 côté client. Le profil scientifique demande d’éviter les accents jusqu’à correction encodage Lua/client.
