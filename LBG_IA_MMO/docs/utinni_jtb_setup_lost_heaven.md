# Utinni + Jawa Toolbox — installation Lost Heaven

**Objectif** : éditer Lost Heaven **offline** (snapshot + terrain) avec le **vrai client SWG**, puis exporter les coords vers le pipeline LBG (`MOD_LBG` → screenplay).

**Liens** :
- [Utinni (GitHub)](https://github.com/ptklatt/Utinni)
- [UtinniPlugins / Jawa Toolbox](https://github.com/ptklatt/UtinniPlugins)
- [Ressource Mod the Galaxy](https://modthegalaxy.com/index.php?resources/utinni.56/)
- Tutoriel vidéo JTB : [YouTube](https://www.youtube.com/watch?v=QVe-oY_Sx1Y)

---

## Prérequis

| Élément | Chemin chez toi |
|---------|-----------------|
| Windows (Utinni = WinForms, pas WSL) | — |
| Client SWG Pre-CU complet (`.tre`) | `J:\swgemu\clients\prime-lbg\` **ou** `J:\swgemu\StarWarsGalaxies\` |
| .NET Framework 4.7.2+ | Windows Update / optional features |
| Visual C++ Redistributable (x86) | Souvent requis pour l’injection client |

> **Recommandé** : pointer Utinni vers **`J:\swgemu\clients\prime-lbg`** (client Prime + patches LBG déjà présents).

---

## 1. Télécharger Utinni

1. Compte [Mod the Galaxy](https://modthegalaxy.com) (gratuit) — ressources et guides communauté.
2. Télécharger **Utinni** :
   - release GitHub : [Utinni v1.0](https://github.com/ptklatt/Utinni/releases/tag/v1.0)
   - ou pack MTG : [resources/utinni.56](https://modthegalaxy.com/index.php?resources/utinni.56/)
3. Extraire dans :

```
J:\swgemu\tools\Utinni\
```

Structure typique : `Utinni.exe`, dossiers `Plugins\`, fichiers `.ini`.

---

## 2. Installer le plugin Jawa Toolbox

1. Télécharger [UtinniPlugins v1.0](https://github.com/ptklatt/UtinniPlugins/releases/tag/v1.0) ou cloner :

```powershell
cd J:\swgemu\tools
git clone https://github.com/ptklatt/UtinniPlugins.git
```

2. Copier le plugin **The Jawa Toolbox** (DLL + dépendances) dans :

```
J:\swgemu\tools\Utinni\Plugins\
```

3. Lancer **Utinni.exe** → vérifier que **The Jawa Toolbox** apparaît dans la liste des plugins.

---

## 3. Configurer le client SWG

Au premier lancement Utinni :

1. **Game path** → `J:\swgemu\clients\prime-lbg`
2. Exécutable cible : **`SWGEmu.exe`** (Utinni injecte dans le client Pre-CU ; `LBGEmu.exe` est le même binaire renommé).
3. Option **offline scene mode** : activer si proposé dans Utinni / JTB.
4. Sauvegarder (`Settings` / `.ini` dans le dossier Utinni).

### Scène de départ Lost Heaven

Dans Jawa Toolbox, configurer le chargement direct (startup scene) :

| Paramètre | Valeur |
|-----------|--------|
| Planète / zone | `tatooine` |
| Position | **x=4749, y=-737, z=1** (ancre MOD_LBG actuelle) |
| Mode | offline / freecam |

Les noms exacts des champs varient selon la version JTB — voir le panneau **Scene** / **Startup** dans l’UI.

---

## 4. Premier test (5 min)

1. Lancer **Utinni** (pas le client seul).
2. Utinni ouvre le client **dans sa fenêtre** (mode éditeur).
3. JTB → **Object Browser** → chercher `shuttleport_tatooine` ou `object/building/tatooine/...`
4. Glisser un bâtiment dans la scène → **gizmo** pour positionner au sol.
5. **Reload snapshot** (menu JTB) — le bâtiment reste sans relancer le client.

Si l’injection échoue : antivirus, lancer Utinni **en administrateur**, vérifier que le client n’est pas déjà ouvert ailleurs.

---

## 5. Templates Lost Heaven (référence)

| POI | Template |
|-----|----------|
| Bazar | `object/building/tatooine/guild_commerce_tatooine_style_01.iff` |
| Banque | `object/building/tatooine/bank_tatooine.iff` |
| Cantina | `object/building/tatooine/cantina_tatooine.iff` |
| Auberge | `object/building/tatooine/hotel_tatooine_general.iff` |
| Starport | `object/building/tatooine/shuttleport_tatooine.iff` |
| Hall combat | `object/building/tatooine/guild_combat_tatooine_style_01.iff` |
| Clinique | `object/building/tatooine/hospital_tatooine.iff` |
| Missions | `object/building/tatooine/salon_tatooine.iff` |
| Mairie | `object/building/tatooine/capitol_tatooine.iff` |
| Artisan | `object/building/tatooine/housing_tatt_style01_med.iff` |
| Logements PNJ | `object/building/tatooine/housing_tatt_style01_small.iff` |
| Porte sud | `object/building/tatooine/filler_building_block_64x32_style_01.iff` |

Catalogue complet : `LBG_IA_MMO/tools/world_editor/scrapaltai_poi_catalog.json`

---

## 6. Chaîne vers le serveur LBG

Une fois les bâtiments bien posés dans JTB :

1. **Noter** pour chaque objet : `template`, `x`, `y`, `z`, `heading` (panneau propriétés JTB ou export si disponible).
2. Enregistrer dans `J:\swgemu\MOD_LBG\lost_heaven_jtb_export.json` (format libre pour l’instant).
3. Côté WSL :

```bash
cd LBG_IA_MMO
# à venir : import_jtb_snapshot.py
python3 tools/world_editor/import_ig_dump.py /mnt/j/swgemu/MOD_LBG/lost_heaven_jtb_export.json -o /mnt/j/swgemu/MOD_LBG/scrapaltai_v7_default.json --snap
bash tools/world_editor/apply_mod_lbg_layout.sh
bash infra/scripts/deploy_core3_ia_bridge_vm.sh --restart
```

4. Validation IG : `lbg_we hub clean` → `lbg_we hub build`

> **Important** : JTB règle le **visuel client**. Le serveur Core3 doit toujours **spawner** les structures (`spawnBuilding`) pour terminaux, cellules et collision multijoueur.

---

## 7. SIE / Sytner (complément terrain)

| Outil | Chemin | Usage |
|-------|--------|--------|
| **Sytner IFF Editor** | `J:\swgemu\sytners_iff_editor_3_11_6_8_release\` | `starting_locations.iff`, datatables |
| **SIE** (MTG) | modthegalaxy.com | `.iff` / assets selon guides MTG |
| **Terrain `.trn`** | guides MTG « Editing the terrain file » | Plateau permanent Tatooine (LAYR/FBIT) |

Workflow long terme : **JTB** pour la ville visible + **`.trn`** pour aplatir le site une fois + **`lbg_we terrain`** pour aligner le serveur.

---

## Dépannage

| Symptôme | Piste |
|----------|--------|
| Client noir / crash à l’injection | Chemin `.tre` incomplet ; tester `StarWarsGalaxies\` |
| Pas d’Object Browser | Attendre fin du chargement des TRE ; relancer Utinni |
| Bâtiments OK offline, KO en ligne | Normal sans deploy screenplay — voir §6 |
| Utinni daté (2020–2021) | Projet stable mais peu maintenu ; forum MTG pour forks/astuces |

---

## Voir aussi

- [`docs/adr/0010-lost-heaven-terrain-first.md`](adr/0010-lost-heaven-terrain-first.md)
- [`tools/world_editor/README_scrapaltai_editor.md`](../tools/world_editor/README_scrapaltai_editor.md)
- [`docs/scrapaltai_starting_locations_mod.md`](scrapaltai_starting_locations_mod.md)
