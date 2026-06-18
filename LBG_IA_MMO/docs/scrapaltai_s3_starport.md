# Scrapaltai S3 — starport et hub Lost Heaven

## Placement automatique (recommandé)

Le screenplay `lbg_lost_heaven_screenplay.lua` pose **les 12 bâtiments** du hub au premier login sur Tatooine (ou dès qu’un compte watchlist est en zone) :

- Ancre **4809, -802** + offsets `lost_heaven_hub.json`
- Export runtime : `ia_bridge/world_poi/scrapaltai.json` (object_id réels)
- Reconstruction après reboot si le starport n’existe plus en monde

```bash
cd LBG_IA_MMO
bash infra/scripts/deploy_core3_ia_bridge_vm.sh --restart
```

Connecter **Teome** (ou tout perso) sur Tatooine → message système `[LBG] Lost Heaven : N/12 batiments + plateau terrain...`.

Le hub crée une **grille de theaters** (`spawnTheaterObject` + flatten) pour aplatir le désert côté client, puis recale chaque bâtiment sur `getWorldFloor`. Si une porte reste en l’air : **`lbg_we hub build`** ou relog.

Pour forcer une nouvelle pose : effacer le flag serveur `lbg_lost_heaven_city_built_v1` (GM) ou supprimer `ia_bridge/world_poi/scrapaltai.json` puis redémarrer.

---

## Option manuelle in-game (World Editor)

**Prérequis** : Teome **Dev+** (`admin_level >= 3`), deploy récent du World Editor.

```bash
cd LBG_IA_MMO
bash infra/scripts/deploy_core3_ia_bridge_vm.sh --restart
```

---

## Checklist IG (~10 min)

Onglet **Spatial** du chat (sans `/` devant `lbg_we`).

| # | Commande | Résultat attendu |
|---|----------|------------------|
| 1 | `lbg_we hub goto` | Téléport **4809, -802** (désert, carte OK) |
| 2 | `lbg_we session on` | `Session ON` |
| 3 | `lbg_we hub anchor` | `last_dump = ancre hub` |
| 4 | Marcher ~20–40 m, viser l’emplacement du shuttle | Choisir l’orientation |
| 5 | `lbg_we dump` | Noter x/y/z (ajuster si besoin) |
| 6 | `lbg_we poi preset starport` | Shuttleport Tatooine spawné ; message `oid=...` |
| 7 | Entrer dans le bâtiment, tester terminal voyage | Navmesh / collision OK |
| 8 | `lbg_we export` | `Export Scrapaltai → ia_bridge/world_poi/scrapaltai.json` |

**Template utilisé** : `object/building/tatooine/shuttleport_tatooine.iff` (shuttle + ticket collector vanilla).

Alternative plus petite :  
`lbg_we poi place poi:lost_heaven_starport object/building/general/shuttleport_general.iff`

---

## Si `spawnBuilding` échoue

- Vérifier **extérieur** (`cell=0` au dump).
- Essayer un autre template (`shuttleport_general.iff`).
- S’éloigner de 5–10 m et refaire `dump` + `preset starport`.
- Logs : `grep -i worldeditor /tmp/core3-clean.log`

---

## Après export

L’agent VM fusionne vers Git (`tools/world_editor/merge_export.py`) :

- `content/core3/world_poi/scrapaltai.json` — POI starport
- `content/core3/locations/lost_heaven_hub.json` — coords structure si starport exporté

Pull le repo local puis commit manuel si l’agent n’a pas push.

---

## Suite S4

- Cantina : `poi:lost_heaven_cantina` + migration roster barman
- Voir [`adr/0009-scrapaltai-lost-heaven.md`](adr/0009-scrapaltai-lost-heaven.md)
