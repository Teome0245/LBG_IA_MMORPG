# Scrapaltai — spawn joueur & patch `starting_locations.iff`

**ADR** : [`adr/0009-scrapaltai-lost-heaven.md`](adr/0009-scrapaltai-lost-heaven.md)  
**Ancre confirmée** : [`content/core3/locations/lost_heaven_hub.json`](../content/core3/locations/lost_heaven_hub.json) — **4809, -802**, hauteur **9**

---

## État actuel (serveur)

| Mécanisme | Statut |
|-----------|--------|
| Redirect login ME → Lost Heaven | **Désactivé (juin 2026)** — `IA_BRIDGE_LOST_HEAVEN_ENABLED = false` dans `ia_bridge_screenplay.lua` ; reprendre quand hub LH déployé |
| Rayon Mos Eisley | 1000 m autour de (3496, -4784) |
| Persistance | Flag `lbg_spawn_lost_heaven_v1:<oid>` — une fois par perso |
| Bots Lia/Nix | Exclus |

Déployer après modification :

```bash
bash infra/scripts/deploy_core3_ia_bridge_vm.sh --restart
```

Test : créer un perso avec départ Mos Eisley → après tutorial / login Tatooine proche ME → message `[LBG] Bienvenue sur Scrapaltai...` + teleport désert.

---

## Cible client (sans redirect)

Fichier retail / patch : **`datatables/creation/starting_locations.iff`**

- Chargé par `PlayerManagerImplementation::loadStartingLocations()` au boot Core3.
- Entrée vanilla **`mos_eisley`** → remplacer par **`lost_heaven`** aux coords hub.
- Commande joueur : `newbieSelectStartingLocation` (zone **tutorial** uniquement).

### Étapes MOD_LBG (Windows)

1. Ouvrir `starting_locations.iff` avec **Sytner IFF Editor** (`J:\swgemu\sytners_iff_editor_...`).
2. Dupliquer une ligne `mos_eisley` → renommer clé ville **`lost_heaven`**.
3. Coords (repère SWG datatable, aligner sur hub) :
   - **X** = 4809
   - **Z** (hauteur) = 9
   - **Y** (plan) = -802
   - **Zone** = `tatooine`
   - **Heading** = 90
4. Option : désactiver / retirer `mos_eisley` de la liste proposée au client.
5. Packager dans `J:\swgemu\MOD_LBG\` + patch client Prime (`clients/prime-lbg`).
6. Redistribuer le patch launchpad / manifeste client.

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
