# M8 — Monde unique Scrapaltai / Lost Heaven

**ADR** : suite [0009](adr/0009-scrapaltai-lost-heaven.md)  
**Config** : [`content/core3/scrapaltai_world.json`](../content/core3/scrapaltai_world.json)

## Objectif

- **Une ville gameplay** : Lost Heaven `(4749, -737)`
- **Spawn joueurs** : port shuttle `(4749, -537)`
- **Planète entière** Scrapaltai (`tatooine`) **parcourable**
- **Purge** : mobs vanilla (cull), pas de voyage inter-planètes, villes vanilla sans contenu LBG
- **Repopulation** progressive via `world_poi` / screenplays LBG
- **Clients** : retail (`lbgemu.exe`) + Godot (`prime-client`)

## Déploiement serveur

```bash
# VM Prime
bash infra/scripts/deploy_core3_ia_bridge_vm.sh --restart

# Tatooine seule planète active (si pas déjà fait)
bash infra/scripts/apply_core3_clean_tatooine_only_vm.sh

# Rebuild hub Lost Heaven (terrain + 12 bâtiments + blue frog)
bash infra/scripts/rebuild_lost_heaven_vm.sh
```

### Comportement au login

| Joueur | Action |
|--------|--------|
| Nouveau / existant | Téléport **une fois** vers Lost Heaven (`lbg_world_m8_v1:<oid>`) |
| Lia / Nix / Mira | Migration vers postes LH dédiés (cantina / starport / training) |
| Déjà à Lost Heaven | Flag posé, pas de téléport |
| Sur autre planète | Renvoyé vers Lost Heaven + message |

### Blue frog

Terminal Character Builder spawné après `hub build` v9, près de la place bazar `(4799, -787)`.

## Client retail

```bash
python3 tools/client_patch/patch_starting_locations.py \
  /chemin/vers/datatables/creation/starting_locations.iff \
  -o /mnt/j/swgemu/MOD_LBG/datatables/creation/starting_locations.iff
```

Puis repackager `MOD_LBG` dans le client `prime-lbg`.

## Client Godot

```bash
python3 tools/map_export/export_tatooine_for_godot.py
```

Carte ±6500 m, POI Lost Heaven + spawn ; villes vanilla marquées `deprecated`.

## Validation IG

1. Créer un perso → apparaît à Lost Heaven
2. Se connecter avec Gally/Teome → migration unique vers starport LH
3. Marcher vers le désert → pas de clamp (mouvement libre)
4. Pas de mobs vanilla (cull actif)
5. Terminal blue frog près du hub
6. Godot : carte affiche Lost Heaven + spawn

## Limites connues

| Élément | Retail | Godot |
|---------|--------|-------|
| Mesh villes vanilla (ME, Bestine…) | Toujours visible | POI masqués (`deprecated`) |
| Terminaux shuttle vanilla | Mesh présent, pas de contenu LBG | N/A |
| Intérieurs cantina ME | Obsolètes — PNJ pilotes en extérieur LH | Snapshots `in_interior` à marquer |
