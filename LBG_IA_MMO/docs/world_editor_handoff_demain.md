# Handoff — World Editor & contenu Mos Eisley (Prime)

**Dernière mise à jour** : 1er juin 2026 (session IG Teome, Mos Eisley).

Document de reprise : ce qui fonctionne, coordonnées validées IG, commandes, suite.

---

## Résumé session 2026-06-01

| Domaine | Statut |
|---------|--------|
| World Editor (`lbg_we` spatial + export) | **OK** (admin compte + perso, merge catalogue) |
| 7 trainers centre ME | **Placés + export** (`roster:mos_trainer_*`, cells 1189634–1189639) |
| Triplon entertainer (Bige / Lyra / Talen) | **Catalogue** + loisir **scène théâtre** |
| Triplon barman cantina (Jax / Sira / Torrik) | **Catalogue** + poste bar `y=1.15` (conversation au comptoir) |
| Cellules cantina / théâtre | **Corrigées** (ancien code inversait 1082877 ↔ 1105853) |

---

## Cellules bâtiment Mos Eisley (référence)

| Cell ID | Zone | Usage LBG |
|---------|------|-----------|
| `1082877` | Cantina (rez-de-chaussée) | Bar, barmans, entrée Lia |
| `1105851` | Cantina (théâtre) | **Scène** — loisir / show entertainers |
| `1105853` | Cantina (mezzanine) | `theater_manager` vanilla (~21.99, 51.19, 64.05) |
| `1189634`–`1189639` | Centre entraînement ME | Posts trainers (1 cell / salle) |

**Attention** : ne pas confondre `1105851` (scène) et `1105853` (mezzanine).

Fichiers : `content/core3/locations/mos_eisley_cantina_bar.json`, `mos_eisley_training_center.json`, commentaires dans `ia_bridge_screenplay.lua`.

---

## Coordonnées validées IG (dump Teome)

### Scène théâtre — loisir entertainers

| Champ | Valeur |
|-------|--------|
| cell | `1105851` |
| x / y / z | `0.34` / `51.19` / `2.13` |
| heading | `173.9` |

Catalogue : `roster:mos_entertainer_trainer` → `binding.cantina`, `binding.home`, `leisure_patrol` (3 points autour de la scène).  
Phase **leisure** → présence `cantina` (show danse) sur la scène ; phase **work** → poste centre (`1189634`).

### Comptoir bar — barmans

| Champ | Valeur |
|-------|--------|
| cell | `1082877` |
| x / z / heading | `7.26` / `-0.89` / `30.2` |
| y (poste client) | **`1.15`** (évite ~3 m derrière le bar, LOS conversation) |

Roster : `roster:mos_eisley_cantina_barman` — `npc:core3_barman_{jax,sira,torrik}`.  
`combat_policy: peaceful_static` en poste.

### Centre entraînement — poste entertainer (travail)

| Champ | Valeur |
|-------|--------|
| cell | `1189634` |
| x / y / z | `0.18` / `-1.49` / `1.13` |
| heading | `348.38` |

---

## World Editor — commandes

Préfixe chat **Spatial** : `lbg_we …` (sans `/`). Alternative client patch : `/lbgwe …`.

| Action | Commande |
|--------|----------|
| Session | `lbg_we session on` \| `off` |
| Position | `lbg_we dump` |
| Statut | `lbg_we status` |
| Placer pilote catalogue | `lbg_we npc place <pilot_id>` |
| Retirer | `lbg_we npc remove <pilot_id>` |
| Persister | `lbg_we export` puis deploy VM |

**Admin** : niveau Dev+ sur **compte** (`ia_bridge/lbg_account_admin.json` + SQL) ou perso `admin_level >= 3`. Voir `docs/core3_account_admin.md`.

**IDs entertainers** (pas `npc:core3_entertainer_trainer_*`) :

- `npc:core3_bige_coto`
- `npc:core3_lyra_velo`
- `npc:core3_talen_ress`

Après changement de coords catalogue : `npc remove` + `dump` au bon endroit + `npc place` + `export`, ou reboot serveur.

---

## Déploiement VM (192.168.0.245)

```bash
cd LBG_IA_MMO
bash infra/scripts/deploy_core3_ia_bridge_vm.sh --restart
bash infra/scripts/diag_world_editor_vm.sh   # Teome connecté
```

Chemins runtime :

```
/opt/lbg-new-mmo-clean/MMOCoreORB/bin/
  scripts/custom_scripts/screenplays/lbg_world_editor_screenplay.lua
  scripts/custom_scripts/screenplays/ia_bridge_screenplay.lua
  ia_bridge/core3_npc_catalog.json
```

Logs : `ssh lbg@192.168.0.245 'tail -f /tmp/core3-clean.log | grep -iE "worldeditor|IaBridge"'`

---

## Lost Heaven / Scrapaltai (S3 starport)

Guide pas à pas : [`docs/scrapaltai_s3_starport.md`](scrapaltai_s3_starport.md)

| Commande | Effet |
|----------|--------|
| `lbg_we hub goto` | Téléport ancre 4809, -802 |
| `lbg_we hub anchor` | Fixe last_dump sur l’ancre |
| `lbg_we poi preset starport` | Pose `shuttleport_tatooine.iff` → `poi:lost_heaven_starport` |

Export → `content/core3/world_poi/scrapaltai.json`

---

## Suite prioritaire (prochaine session)

1. **Barman** : `vendor_sell` (rachat inventaire), journal quête SWG si besoin.
2. **Reposition IG** : si un PNJ reste à l’ancienne coordonnée → `reset_pilot` ou `lbg_we npc remove` + `place`.
3. **World Editor client** : TRE `/lbgwe` optionnel — voir `docs/client_patch_lbgwe.md`, `docs/troubleshoot_lbgemu_launch.md`.
4. **Smoke** : `smoke_core3_ia_phase_c4_entertainer_roster_lan.sh`, phase C NPC.

---

## Historique — problèmes World Editor (mai 2026)

Résolus ou contournés en session récente :

- `isDevPlus` ne regardait que le perso → export silencieux ; fix `getEffectiveAdmin`.
- `npc place` sans entrée catalogue → `commoner` ; fix `resolvePilotCfgFromCatalogJson`.
- Test `status` ne remplit pas `world_editor_session.json` → utiliser `session on`.

Si **spatial** ne répond plus : relog Teome, `diag_world_editor_vm.sh`, vérifier `admin_level` MySQL.

---

## Fichiers clés

| Fichier | Rôle |
|---------|------|
| `content/core3/core3_npc_catalog.json` | Rosters, posts, loisir, barmans |
| `content/core3/world_poi/tatooine.json` | POI / slots export WE |
| `content/core3/lua/lbg_world_editor_screenplay.lua` | Commandes WE |
| `content/core3/lua/ia_bridge_screenplay.lua` | Lifecycle, cantina, théâtre |
| `docs/world_editor_plan.md` | Plan v1 éditeur |
| `docs/core3_ia_phase_c4_entertainer_roster.md` | Roster entertainer |
| `docs/core3_ia_phase_c4b_game_time.md` | Cycle travail/repos/loisir |
| `docs/plan_client_lbg_godot.md` | Faisabilité client Godot sans SWG |

---

## Critères de succès (rappel)

1. `lbg_we session on` → message `[WorldEditor] Session ON`.
2. `lbg_we dump` en intérieur → `cell` ≠ 0.
3. `lbg_we export` → merge Git / VM `core3_npc_catalog.json` à jour.
4. Barman : conversation au comptoir ; entertainer en loisir : visible sur scène `1105851`.
