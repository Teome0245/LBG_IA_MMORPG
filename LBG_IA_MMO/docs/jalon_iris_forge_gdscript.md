# Jalon Iris — forge GDScript automatique (M9)

**Date** : 2026-07-12  
**Statut** : **L1 staging** — apply L2 optionnel  
**Persona** : **Iris** (`dev_godot`)

---

## Objectif

Transformer les **gaps M9** détectés par les sondes en **patches GDScript / scènes / config** proposés, sans écraser le Prime Client sans garde-fou.

```
Sondes M9 → gaps → iris_gdscript_forge → staging/.iris_forge/ → (option) apply Prime Client
```

---

## Comportement

| Niveau | Variable | Effet |
|--------|----------|-------|
| **L1** (défaut) | `LBG_IRIS_FORGE_AUTO_APPLY=0` | Écrit dans `{prime-client}/.iris_forge/staging/{task_id}/` + manifest JSON |
| **L1 apply** | `LBG_IRIS_FORGE_AUTO_APPLY=1` | Copie les fichiers manquants vers Prime Client (templates M9) |
| **L2** | Token Pilot + revue humaine | Merge manuel ou Cursor pour patches complexes |

---

## Gaps couverts (recettes)

| Gap | Fichier cible |
|-----|---------------|
| minimap script/scène/config | `scripts/minimap_hud.gd`, `scenes/ui/minimap_hud.tscn`, `config/minimap_config.json` |
| MinimapHud non branchée | patch `scenes/main.tscn` |
| planet map / waypoints | `scripts/planet_map_panel.gd`, `scenes/ui/planet_map_panel.tscn`, `scripts/waypoint_store.gd`, configs |
| PlanetMapPanel non branchée | patch `scenes/main.tscn` |

Templates canoniques : `orchestrator/team/forge_templates/iris_m9/`

---

## Usage

### Pilot `#/team`

- Preset **Iris forge M9** (dev_godot + `iris_forge: true`)
- Presets Iris M9 / M9 minimap déclenchent la forge si gaps

### Autoconsult

Les followups Iris spawnés avec `iris_forge: true` après round Thémis.

### Variables

```bash
LBG_IRIS_FORGE_ENABLED=1
LBG_IRIS_FORGE_AUTO_APPLY=0
LBG_IRIS_FORGE_STAGING_DIR=   # optionnel ; défaut prime-client/.iris_forge/staging
LBG_PRIME_CLIENT_ROOT=/opt/new_mmo/prime-client
```

---

## Fichiers

| Fichier | Rôle |
|---------|------|
| `orchestrator/team/iris_gdscript_forge.py` | Moteur forge |
| `orchestrator/team/m9_map_workflow.py` | Branche forge si `dev_godot` / Iris |
| `orchestrator/tests/test_iris_gdscript_forge.py` | Tests |

---

### Mode LLM (REASON backend)

Si `LBG_IRIS_FORGE_LLM=1` (défaut) :

1. Templates d'abord (recettes M9 + Hermès réseau)
2. Gaps restants → `reason_llm` (Ollama 110 / API)
3. Smoke obligatoire (`LBG_IRIS_FORGE_SMOKE_REQUIRED=1`)
4. Apply seulement si smoke OK + `LBG_IRIS_FORGE_AUTO_APPLY=1`

Recettes Hermès : `network_bridge.gd`, patches `player_controller` (goto UDP) via LLM.

Variables REASON : `LBG_REASON_BASE_URL`, `LBG_REASON_MODEL` — voir `docs/architecture_tri_backend_hybride.md`.

- Recettes **M9b/M9c** uniquement (pas Core3, pas Hermès réseau)
- Pas de génération LLM — templates + patch `main.tscn` déterministes
- Gaps pipeline repo (export POI, smokes infra) → Héphaïstos / humain

---

## Roadmap

1. Forge LLM assistée (Claude) avec validation smoke obligatoire
2. Recettes Hermès (network_bridge, goto UDP)
3. Apply L2 via token Pilot `#/team`
