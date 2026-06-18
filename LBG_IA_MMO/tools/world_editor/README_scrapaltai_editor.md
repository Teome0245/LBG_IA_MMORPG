# Éditeur Scrapaltai v2 (client SWG + outil 2D)

Outil 2D pour concevoir **Lost Heaven** avec le **client SWG d’origine** (`SWGEmu.exe`) et le screenplay serveur — pas de Godot pour cette phase.

## Lancer l’éditeur visuel

```bash
cd LBG_IA_MMO/tools/world_editor
python3 -m http.server 8765
```

Ouvrir : [http://localhost:8765/scrapaltai_editor.html](http://localhost:8765/scrapaltai_editor.html)

### Onglets

| Onglet | Usage |
|--------|--------|
| **Ville (grille)** | Glisser-déposer les POI ; centre = place bazar ; cercle orange = plateau serveur |
| **Planète Tatooine** | Carte SVG calibrée (coords serveur) ; clic = ancre ; pan/zoom |

### Contrôles

- **Molette** : zoom (ville ou planète)
- **Shift + glisser** : pan
- **Snap grille** : aligne sur l’espacement (100 m par défaut)
- Bâtiments en **rouge** = collision (espacement &lt; minimum)

## Workflow client SWG (v2)

1. IG Tatooine, compte Dev+ : `lbg_we session on`
2. Se placer au centre bazar (ou bâtiment à caler) : `lbg_we dump` ou `lbg_we dump json`
3. Copier le message chat → **Import dump IG** dans l’éditeur → **Définir ancre**
4. Ajuster la grille ville → **Exporter JSON** → enregistrer dans `J:\swgemu\MOD_LBG\`
5. Appliquer et déployer :

```bash
cd LBG_IA_MMO
bash tools/world_editor/apply_mod_lbg_layout.sh
# ou : bash tools/world_editor/apply_mod_lbg_layout.sh /mnt/j/swgemu/MOD_LBG/mon_layout.json 9
bash infra/scripts/deploy_core3_ia_bridge_vm.sh --restart
# IG : lbg_we hub clean → lbg_we hub build
```

Staging layouts : `J:\swgemu\MOD_LBG\` = `/mnt/j/swgemu/MOD_LBG/` sous WSL.

### Import hors navigateur (CLI)

```bash
# Dump chat ou JSON one-liner
python3 tools/world_editor/import_ig_dump.py mon_dump.txt -o layouts/from_ig.json --snap

# Session VM (ia_bridge/world_editor_session.json copiée en local)
python3 tools/world_editor/import_ig_dump.py world_editor_session.txt --layout layouts/scrapaltai_v7_default.json -o layouts/from_session.json

# Export scrapaltai.json (après lbg_we export)
python3 tools/world_editor/import_ig_dump.py ../../content/core3/world_poi/scrapaltai.json -o layouts/from_export.json --snap
```

## Appliquer le layout → serveur

```bash
python3 tools/world_editor/apply_scrapaltai_layout.py tools/world_editor/layouts/mon_layout.json --bump-version 8
python3 tools/world_editor/apply_scrapaltai_layout.py layouts/scrapaltai_v7_default.json --dry-run
python3 tools/world_editor/apply_scrapaltai_layout.py --export-from-screenplay layouts/imported.json
```

## Fichiers

| Fichier | Rôle |
|---------|------|
| `scrapaltai_editor.html` | UI v2 (ville + planète + import dump) |
| `scrapaltai_import.js` | Parse dump / session / export JSON |
| `import_ig_dump.py` | Import CLI → layout JSON |
| `assets/tatooine_map.svg` | Fond carte Tatooine (schéma calibré) |
| `tatooine_map_config.json` | Bounds SWG ±6500, north-up |
| `scrapaltai_poi_catalog.json` | Templates, couleurs, emprises |
| `layouts/*.json` | Layouts versionnés (repo) |
| `apply_scrapaltai_layout.py` | Patch screenplay + `lost_heaven_hub.json` |
| `apply_mod_lbg_layout.sh` | Apply depuis `J:\swgemu\MOD_LBG\` (WSL) |

## Éditeur in-game (`lbg_we`)

| Commande | Effet |
|----------|--------|
| `lbg_we dump` | Coords chat `x=… y=…` + session VM |
| `lbg_we dump json` | One-liner JSON pour coller dans l’éditeur |
| `lbg_we export` | `scrapaltai.json` (POI posés en session) |
| `lbg_we hub goto\|clean\|build` | Hub Lost Heaven |

**SOE World Editor client** : non branché — on reste sur client retail + `lbg_we` + cet éditeur 2D.

## Roadmap (client SWG only)

1. **v1** — grille 2D + export Lua ✅  
2. **v2** — carte Tatooine + import dump IG ✅  
3. **v3** — `lbg_we terrain flatten|plateau` in-game (branché `addTerrainFlatten`)  
4. **v4** — sync bidirectionnelle auto (agent VM → layout JSON)  

Godot / gateway 3D : **reporté** — voir `docs/plan_client_godot_prime_rendu.md` si besoin plus tard.

## Voir aussi

- [`docs/world_editor_plan.md`](../../docs/world_editor_plan.md)
- [`docs/adr/0009-scrapaltai-lost-heaven.md`](../../docs/adr/0009-scrapaltai-lost-heaven.md)
