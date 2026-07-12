# Clients Godot — 2D top-down vs 3D (parallèle)

**Statut** : décision produit juillet 2026 — **priorité = Prime Client 2D** ; 3D en pause (retour plus tard, éventuellement modèles WC3-style).

## Décision actuelle (juil. 2026)

| Priorité | Client | Statut |
|----------|--------|--------|
| **Active** | **Prime Client** (2D top-down) | Développement principal — bots, carte, POI, Core3 |
| **Pause** | Prime Client 3D | Labo assets validé (drone robot01) — reprise plus tard |
| **Piste future** | Hybride type **Warcraft 3** | Sprites 2D + quelques meshes 3D en vue top-down — à définir |

> Pipeline Infographiste_IA et `lbg_client_godot` restent en place pour la reprise 3D.

## Vue d’ensemble

| Client | Projet Godot | Mode | Rôle principal |
|--------|--------------|------|----------------|
| **Prime Client** | `new_mmo/prime-client` | **2D top-down** | Observateur Core3 Prime — bots, carte, POI, debug IA |
| **Prime Client 3D** | `LBG_IA_MMO/lbg_client_godot` | **3D** | Rendu 3D Prime (gateway `:50000`) + lab assets GLB |

> **Politique juillet 2026** : seuls les clients **Core3 Prime** sont maintenus.  
> Le bac à sable Terre1 (`mmmorpg_server`, port 7733) est **hors produit** (legacy / smoke tests uniquement).  
> Dans Godot le projet s’affiche **« Prime Client 3D »** (dossier inchangé : `lbg_client_godot`).

Les deux peuvent partager la **même source de vérité** (snapshots Core3, `zone_feed.py`, gateway WS) — voir [`plan_client_godot_prime_rendu.md`](plan_client_godot_prime_rendu.md).

## Godot 4.6.1 (poste dev)

```
J:\mmmorpg\Godot_v4.6.1-stable_win64\Godot_v4.6.1-stable_win64.exe
```

Dans le gestionnaire de projets : **Scanner** si un chemin WSL apparaît tronqué (`lbg_cl…`).

| Projet à ouvrir | Chemin WSL |
|-----------------|------------|
| Prime Client | `/home/sdesh/projects/new_mmo/prime-client` |
| Prime Client 3D | `/home/sdesh/projects/LBG_IA_MMORPG/LBG_IA_MMO/lbg_client_godot` |

> `LBG Client (4.3)` et `mmmorpg` (J:) = **archives** — ne pas utiliser.

## Quand utiliser lequel ?

| Besoin | Client recommandé |
|--------|-------------------|
| Vérifier positions bots, POI, hub LH, 26+ PNJ | **Prime Client** (2D) |
| Tester un GLB, échelle, cantina 3D, drone IA | **Prime Client 3D** (pause) |
| **Sprites unités top-down** (bots, NPC) | **Infographiste_IA** → **Prime Client** |
| Dialogue IA / gateway Prime | Les deux (Prime M3+, LBG POC réseau) |
| Perf / itération rapide gameplay | **2D** d’abord |
| Démo visuelle / intégration assets | **3D** |

Stratégie : **ne pas bloquer l’un sur l’autre** — un protocole commun permet de garder les deux ou de n’en garder qu’un plus tard.

## Assets 3D déjà intégrés (LBG Client)

| Asset | Chemin | Scène test |
|-------|--------|------------|
| Drone steampunk robot01 | `assets/props/drones/robot01_round_godot.glb` | `scenes/dev/Robot01Preview.tscn` (F6) |

Pipeline source : repo **Infographiste_IA** (ComfyUI + TripoSR).  
Guide import : [`pipeline_assets_swg_godot.md`](pipeline_assets_swg_godot.md), [`lbg_client_godot/assets/props/README.md`](../lbg_client_godot/assets/props/README.md).

## Lancement rapide

### Prime Client (2D)

```bash
# WSL — si godot4 en PATH
godot4 --path /home/sdesh/projects/new_mmo/prime-client
```

Snapshots live : `tools/zone_observer/zone_feed.py --watch` — voir [`new_mmo/prime-client/README.md`](../../new_mmo/prime-client/README.md).

### LBG Client (3D)

1. Ouvrir `lbg_client_godot/project.godot` dans Godot 4.6.1
2. Laisser importer les GLB (`assets/`)
3. **F6** sur `scenes/dev/Robot01Preview.tscn` ou **F5** sur `Login.tscn` pour le POC réseau

## Liens

| Doc | Sujet |
|-----|--------|
| [`client_dual_launchpad.md`](client_dual_launchpad.md) | Clients **natifs** PreCu / Prime (`SWGEmu.exe` / `lbgemu.exe`) — hors Godot |
| [`plan_client_lbg_godot.md`](plan_client_lbg_godot.md) | POC réseau LBG Client |
| [`jalon_infographiste_ia.md`](jalon_infographiste_ia.md) | Pont assets IA → Godot |

## Suite possible

- [x] ~~Choix priorité client~~ → **2D TopDown d'abord**
- [ ] Aligner contrat WS / snapshots entre Prime 2D et LBG 3D (quand reprise 3D)
- [ ] Étude hybride WC3 (mesh 3D + caméra ortho / billboards)
- [ ] Premier humanoïde GLB dans LBG Client 3D (quand reprise)
