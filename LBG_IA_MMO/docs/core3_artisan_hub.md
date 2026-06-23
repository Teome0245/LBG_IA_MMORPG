# Hub artisan LBG — Phase 1 (distributeur Mod+)

Hub de test craft pour comptes **moderator+** (`admin_level >= 2`). Emplacement : centre d'entraînement Mos Eisley (cell `1189639`).

## Accès

- **Compte** : tous les personnages d'un compte Mod+ (cache `ia_bridge/lbg_account_admin.json`, regénéré au deploy).
- **World Editor** reste Dev+ (niveau 3) — seul le cache inclut désormais les Mod.

## Aller au hub

```text
housing_enter|Teome|tatooine|0|0|0|artisan_hub
```

Ou en jeu (chat Spatial, onglet Spatial) :

```text
lbg_artisan tp
```

## Commandes Spatial

| Commande | Effet |
|----------|--------|
| `lbg_artisan help` | Aide |
| `lbg_artisan list` | Objets (outils, stations) |
| `lbg_artisan listres` | Ressources craftables |
| `lbg_artisan give weapon_tool` | Objet tangible |
| `lbg_artisan res steel` | 10 000 unités d'acier (C++ requis) |
| `lbg_artisan res copper 15000` | Quantité personnalisée (max 30 000) |
| `lbg_artisan kit workshop_starter` | Kit outils |
| `lbg_artisan reskit craft_essentials` | Pack ressources |
| `lbg_artisan tp` | Téléport hub |

## Pont IA (`pending.jsonl`)

```text
dispense|Teome|tatooine|0|0|0|weapon_tool
dispense|Teome|tatooine|0|0|0|kit:workshop_starter
dispense|Teome|tatooine|0|0|0|res:steel
dispense|Teome|tatooine|0|0|0|res:steel:15000
dispense|Teome|tatooine|0|0|0|reskit:mineral_pack
```

## Hub IG (spawn auto)

- Terminal banque (distributeur)
- Terminal **Bazaar** (vente aux enchères vanilla)
- 4 stations craft publiques

## Ressources dynamiques (Phase 2)

Nécessite **rebuild** `core3-clean` avec `iaGiveResourceSample` :

```bash
bash LBG_IA_MMO/infra/scripts/build_core3_antigravity_vm.sh --sync
bash LBG_IA_MMO/infra/scripts/install_core3_clean_after_vm_build.sh
```

Sans rebuild : outils/stations OK ; `lbg_artisan res …` affiche un message d'attente.

Catalogue : `content/core3/core3_resource_samples.json` (~25 types + 2 kits).

## Fichiers

| Fichier | Rôle |
|---------|------|
| `content/core3/core3_artisan_dispenser.json` | Objets + coords hub |
| `content/core3/core3_resource_samples.json` | Ressources craft |
| `content/core3/lua/lbg_artisan_hub_screenplay.lua` | Runtime |
| `new_mmo/.../DirectorManager.cpp` | `iaGiveResourceSample` |
| `ia_bridge/artisan_dispense_audit.jsonl` | Audit |

## Déploiement

```bash
bash LBG_IA_MMO/infra/scripts/deploy_core3_ia_bridge_vm.sh --restart
```

## Phase 3 (à venir)

- Terminal SUI dédié (fork Character Builder)
- Produits finis (schematics)
- Vendeurs PNJ IA réapprovisionnés via `core3_economy.json`
