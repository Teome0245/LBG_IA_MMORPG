# Prime Client 3D (Godot)

Client **Godot 4.6** — **Core3 Prime uniquement** (gateway `lbg-ws/1`, port **50000**).  
Dossier historique : `lbg_client_godot`. Monde 3D, avatars GLB, assets Infographiste_IA.

| Document | Contenu |
|----------|---------|
| [`../docs/clients_2d_3d.md`](../docs/clients_2d_3d.md) | **2D Prime vs 3D LBG** — stratégie parallèle |
| [`../docs/plan_client_godot_prime_rendu.md`](../docs/plan_client_godot_prime_rendu.md) | **Objectif produit** (monde + joueur + serveur) |
| [`../docs/plan_client_lbg_godot.md`](../docs/plan_client_lbg_godot.md) | POC réseau, options gateway |

## État actuel (POC)

Connexion **gateway Core3 Prime** (50000) — mode observateur / capsules, cantina placeholder 3D.

## Prérequis

- Godot **4.6.1** : `J:\mmmorpg\Godot_v4.6.1-stable_win64\Godot_v4.6.1-stable_win64.exe`
- Gateway Prime actif (VM **246**, port **50000**)

```bash
bash infra/scripts/run_lbg_gateway_vm.sh
```

## Lancer le client

1. Ouvrir ce dossier dans Godot : **Importer** → `lbg_client_godot/project.godot`
2. **F5** (scène principale `Login.tscn`)
3. Hôte **`192.168.0.246`**, port **50000**, nom joueur → **Connexion**
   - Snapshots Prime + dialogue IA + joueurs zone (Teome/Lia/Nix via `lbgemu` — capsules turquoise `[lbgemu]`)
4. **F6** `scenes/dev/Robot01Preview.tscn` pour tester un GLB sans réseau
5. En monde : **ZQSD/WASD** — **Tab** = changer de PNJ cible — **Entrée** dans le chat = parler au PNJ

### Gateway Prime (port 50000)

```bash
bash infra/scripts/run_lbg_gateway_vm.sh
# ou en local :
LBG_GATEWAY_SNAPSHOTS=content/core3/ia_bridge/npc_snapshots.json \
PYTHONPATH=. python3 services/lbg_gateway/main.py
```

## Structure

| Chemin | Rôle |
|--------|------|
| `autoload/Network.gd` | WebSocket, `hello`, `move` |
| `autoload/GameState.gd` | Cache entités / `player_id` |
| `autoload/Config.gd` | Hôte / port |
| `scenes/Login.tscn` | Connexion |
| `scenes/World.tscn` | Monde 3D + entités |
| `scenes/EntityView.tscn` | Humanoïde (GLB / placeholder) ou capsule secours |
| `scenes/avatars/` | `AvatarLibrary`, `BaseHumanoid`, `PlaceholderHumanoid` |
| `scenes/props/Robot01Drone.tscn` | Drone steampunk IA (pivot sol + vol) |
| `scenes/dev/Robot01Preview.tscn` | Prévisualisation échelle vs humain 1,6 m |
| `assets/props/drones/` | GLB props (robot01) |
| `assets/avatars/manifest.json` | Mapping espèce / template → GLB |

## Smoke sans Godot

```bash
bash infra/scripts/smoke_lbg_client_ws_phase0.sh
bash infra/scripts/smoke_lbg_client_ws_phase0.sh --host 127.0.0.1
```

## Prime — mode observateur

Quand Teome / Lia / Nix sont en ligne sur lbgemu, le client **suit** le premier snapshot valide (souvent Teome) et affiche les autres joueurs en **turquoise** `[lbgemu]`. Pas de déplacement ZQSD (lecture seule). HUD : `observateur lbgemu`.

## Avatars (pilier C1)

Par défaut : **silhouette humanoïde** (`PlaceholderHumanoid.tscn`). Dès qu’un export SWG existe :

1. Placer le GLB dans `assets/avatars/base/human_male_base.glb`
2. Relancer Godot — `AvatarLibrary` le détecte via `manifest.json`

Guide : [`../docs/pipeline_assets_swg_godot.md`](../docs/pipeline_assets_swg_godot.md).

### Drone steampunk (Infographiste_IA)

1. GLB : `assets/props/drones/robot01_round_godot.glb` (déjà copié)
2. Ouvrir le projet → laisser Godot importer le GLB
3. **F6** sur `scenes/dev/Robot01Preview.tscn` pour valider échelle (~0,55 m) et pivot
4. Décor cantina : instance auto dans `CantinaInterior` (activer la cantina dans `World` si besoin)

Détails pivot/vol : [`assets/props/README.md`](assets/props/README.md).

## Suite (Phase 3)

- `move` Godot → `pending.jsonl` (opt-in gateway, coords cantina à venir)
- Assets maps LBG (GLB)
- `CharacterSelect.tscn` si auth SQL
