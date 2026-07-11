# Jalon client Godot ↔ sidecar Core3 Prime (246)

**Date** : 2026-07-11  
**Statut** : jalon M1 livré (mirroring passif) — M3/M5 SOE live en parallèle

---

## Cible

Le client **Godot 2D Prime** (`new_mmo/prime-client`) affiche les bots IA (Lia, Nix, Mira…) alimentés par le **sidecar HTTP** sur **VM 246:8791**, sans dupliquer la logique orchestrateur.

| Couche | Artefact | VM / chemin |
|--------|----------|-------------|
| Sidecar IA | `tools/core3_ia_sidecar/` | **246** `:8791` |
| Miroir client | `new_mmo/client-prime-lbg/sidecar_mirror.py` | poste dev / WSL |
| Viewer Godot | `new_mmo/prime-client/` | Godot 4.6 |
| Orchestrateur | `player_ia_probe`, équipe `#/team` | **140** |

> Le sidecar n’est **pas** le protocole joueur SOE. C’est l’API **IA ↔ Core3** (snapshots, think, enqueue). Le client Godot consomme les **snapshots** ; le gameplay live passe par SOE UDP (`soe_handshake.py`).

---

## Démarrage rapide (3 terminaux)

### 1. Prérequis LAN

```bash
curl -s http://192.168.0.246:8791/healthz
curl -s "http://192.168.0.246:8791/v1/player-snapshot?player=Lia"
```

Attendu : `healthz` OK, snapshots `online: true` pour Lia/Nix.

### 2. Miroir sidecar → cache Godot

```bash
cd /home/sdesh/projects/new_mmo/client-prime-lbg
bash run_sidecar_mirror.sh
# ou une fois : bash run_sidecar_mirror.sh --once
```

Écrit :
- `prime-client/cache/player_snapshots.json`
- `prime-client/cache/zone_feed.json`

### 3. Godot

```bash
godot4 --path /home/sdesh/projects/new_mmo/prime-client
```

Le `SnapshotBridge` poll `cache/zone_feed.json` (config `config/snapshot_paths.json`).

### 4. Validation orchestrateur (optionnel)

```bash
bash LBG_IA_MMO/infra/scripts/smoke_godot_sidecar_mirror_lan.sh
# ou tâche équipe #/team → Sonde joueurs IA
```

---

## Variables

| Variable | Défaut | Rôle |
|----------|--------|------|
| `SIDECAR_URL` | `http://192.168.0.246:8791` | Base HTTP sidecar |
| `CACHE_DIR` | `../prime-client/cache` | Sortie JSON Godot |
| `BOTS` | `lia,nix,mira,kael` | Bots pollés |
| `LBG_CORE3_SIDECAR_URL` | idem (orchestrateur 140) | Sonde équipe `player_ia` |

---

## Modes d’intégration

| Mode | Complexité | Fichiers |
|------|------------|----------|
| **M1 — Miroir HTTP** (recommandé) | Faible | `sidecar_mirror.py`, `SnapshotBridge` |
| **M3 — SOE live** | Moyenne | `soe_handshake.py` + Godot UDP `:12345` |
| **M5 — Play ZQSD** | Élevée | `prime_controller.py` + `:12346` |

Port ZoneServer Prime : **44563** (pas 44463).

---

## Prochaines étapes (hors jalon M1)

- [ ] `lbg-ws/2` + `LbgZoneBridge` C++ (client 3D `lbg_client_godot/` autoritaire)
- [ ] Gateway `:50000` aligné sur Prime
- [ ] HTTP natif dans `snapshot_bridge.gd` (optionnel si miroir Python suffit)
- [ ] Smoke Godot headless CI

---

## Liens

- [`runbook_promotion_prototype_core3.md`](runbook_promotion_prototype_core3.md)
- [`core3_ia_player_bridge.md`](core3_ia_player_bridge.md)
- [`plan_client_godot_prime_rendu.md`](plan_client_godot_prime_rendu.md)
- [`audit_reunification_projet_2026-07-11.md`](audit_reunification_projet_2026-07-11.md)
