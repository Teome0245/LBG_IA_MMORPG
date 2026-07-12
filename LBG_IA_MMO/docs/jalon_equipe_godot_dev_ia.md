# Jalon — Équipe dev Godot IA (Iris + Hermès)

**Date** : 2026-07-12  
**Statut** : actif

## Nouveau rôle `dev_godot`

Complète `dev_game` (Dédale / Core3 / forge générale) avec des **agents Godot spécialisés**.

| Persona | Rôle API | Domaine | Timer |
|---------|----------|---------|-------|
| **Iris** | `dev_godot` + `godot_dev_persona: iris` | Prime Client 2D, M9, UI, GDScript | `lbg-team-godot-dev-job` |
| **Hermès** | `dev_godot` + `godot_dev_persona: hermes` | SOE M3/M5, ZB, gateway lbg-ws/2 | idem |

Déclarations : `agents/declarations/godot_dev_iris.json`, `godot_dev_hermes.json`

## Équipe virtuelle complète (2026-07)

| Rôle | Persona | Domaine |
|------|---------|---------|
| pm | Thémis | Jalons, réunification |
| qa | Argus | Smokes LAN |
| ops | Héphaïstos | Infra, sync VM, Ollama |
| dev_game | Dédale | Core3 gameplay, build Vulcan |
| **dev_godot** | **Iris / Hermès** | **Godot Prime Client** |
| dev_game | Pygmalion | Assets 3D/2D (infographiste) |
| player_ia | Chœur | Bots Lia/Nix Prime |

## Pilot presets

| Preset | Agent |
|--------|-------|
| **Iris M9** | dev_godot iris → M9 full |
| **Iris carte M** | dev_godot iris → M9c |
| **Hermès SOE** | dev_godot hermes → client_live |

## Install timer (140)

```bash
bash infra/scripts/install_team_godot_dev_job_vm.sh
bash infra/scripts/install_team_m9_map_job_vm.sh
```

## Variables

```bash
LBG_TEAM_GODOT_DEV_JOB_ENABLED=1
LBG_TEAM_M9_AUTO_REMEDIATE=1
LBG_TEAM_M9_FOLLOWUP_ENABLED=1
LBG_PRIME_CLIENT_ROOT=/home/sdesh/projects/new_mmo/prime-client
```

## Followup M9

Échec M9 → PM + **Iris (dev_godot)** + Pygmalion (texture) + ops (sync VM).
