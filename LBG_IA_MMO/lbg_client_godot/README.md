# LBG Client Godot

Client **Godot 4.2+** — cible : **même Core3 Prime** que lbgemu, monde 3D habillé, avatars détaillés.

| Document | Contenu |
|----------|---------|
| [`../docs/plan_client_godot_prime_rendu.md`](../docs/plan_client_godot_prime_rendu.md) | **Objectif produit** (monde + joueur + serveur) |
| [`../docs/plan_client_lbg_godot.md`](../docs/plan_client_lbg_godot.md) | POC réseau, options gateway |

## État actuel (POC)

Connexion **Terre1** (7733) ou **gateway observateur** Prime (50000) — capsules debug, plan vert / cantina non modélisée.

## Prérequis

- [Godot 4.2+](https://godotengine.org/download)
- Serveur WS actif sur la VM MMO (port **7733** par défaut)

```bash
# Depuis LBG_IA_MMO (si service systemd déjà installé)
ssh lbg@192.168.0.245 'systemctl status lbg-mmmorpg-ws'

# Ou lancer en local pour test
cd LBG_IA_MMO
python -m mmmorpg_server
```

## Lancer le client

1. Ouvrir ce dossier dans Godot : **Importer** → `lbg_client_godot/project.godot`
2. **F5** (scène principale `Login.tscn`)
3. Choisir le serveur :
   - **Terre1 — mmmorpg (7733)** : bac à sable + **dialogue PNJ** (si `MMMORPG_IA_BACKEND_URL` actif sur la VM)
   - **Tatooine Prime — gateway (50000)** : snapshots + **dialogue IA** + **joueurs zone** (Teome/Lia/Nix via `lbgemu` si connectés — capsules turquoise `[lbgemu]`)
4. Hôte `192.168.0.245`, nom joueur → **Connexion**
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

## Suite (Phase 3)

- `move` Godot → `pending.jsonl` (opt-in gateway, coords cantina à venir)
- Assets maps LBG (GLB)
- `CharacterSelect.tscn` si auth SQL
