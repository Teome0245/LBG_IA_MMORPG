# Scrapaltai — spawn joueur & patch `starting_locations.iff`

**ADR** : [`adr/0009-scrapaltai-lost-heaven.md`](adr/0009-scrapaltai-lost-heaven.md)  
**Ancre confirmée** : [`content/core3/scrapaltai_world.json`](../content/core3/scrapaltai_world.json) — spawn **4749, -537**, hauteur terrain **~1**

---

## État actuel (serveur M8)

| Mécanisme | Statut |
|-----------|--------|
| Redirect login → Lost Heaven | **Actif** — `IA_BRIDGE_LOST_HEAVEN_ENABLED = true` |
| Migration tous persos (1×) | Flag `lbg_world_m8_v1:<oid>` |
| Bots Lia/Nix/Mira | Exclus |
| Blue frog | Spawn auto après `hub build` v9 |

Déployer après modification :

```bash
bash infra/scripts/deploy_core3_ia_bridge_vm.sh --restart
```

Test : créer un perso avec départ Mos Eisley → **reste proche ME** (redirect LH désactivé juin 2026). Pas de message Scrapaltai tant que `IA_BRIDGE_LOST_HEAVEN_ENABLED = false`.

---

## Cible client (sans redirect)

Fichier retail / patch : **`datatables/creation/starting_locations.iff`**

- Chargé par `PlayerManagerImplementation::loadStartingLocations()` au boot Core3.
- Entrée vanilla **`mos_eisley`** → remplacer par **`lost_heaven`** aux coords hub.
- Commande joueur : `newbieSelectStartingLocation` (zone **tutorial** uniquement).

### Étapes MOD_LBG (Windows)

1. Ouvrir `starting_locations.iff` avec **Sytner IFF Editor** (`J:\swgemu\sytners_iff_editor_...`).
2. Dupliquer une ligne `mos_eisley` → renommer clé ville **`lost_heaven`**.
3. Coords (repère SWG datatable, aligner sur `scrapaltai_world.json`) :
   - **X** = 4749
   - **Z** (hauteur) = 1
   - **Y** (plan) = -537
   - **Zone** = `tatooine`
   - **Heading** = 90
4. Option : désactiver / retirer `mos_eisley` de la liste proposée au client.
5. **Automatique** : `python3 tools/client_patch/patch_starting_locations.py starting_locations.iff -o MOD_LBG/...`
6. Packager dans `MOD_LBG` + patch client Prime (`clients/prime-lbg`).

### Strings client (optionnel)

Renommer l’entrée affichée « Mos Eisley » → **Lost Heaven, Scrapaltai** dans les string tables liées à la création de perso.

---

## Ordre des phases (rappel)

| Phase | Action |
|-------|--------|
| S1 | Ancre IG | **Fait** |
| S2 | `starting_locations.iff` | Ce document |
| S2b | Redirect Lua | **Fait** (secours) |
| S3 | POI `poi:lost_heaven_starport` | World Editor |
