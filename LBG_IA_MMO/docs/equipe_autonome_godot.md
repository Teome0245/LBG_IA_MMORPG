# Équipe virtuelle autonome — Godot + sidecar 246 + lbg-ws/2

**Objectif** : demain matin, la Team pilote les deux pistes client **sans intervention manuelle** (timers + followups auto).

---

## Boucle autonome (VM 140)

```mermaid
flowchart TD
  T[Timer 6h godot-supervisor] --> QA[Tâche qa godot_supervisor]
  QA -->|OK| DONE[Log + #/team]
  QA -->|KO| FU[Followup auto]
  FU --> PM[pm brief Godot]
  FU --> DEV[dev_game lbg-ws/2]
  FU --> PIA[player_ia re-sonde]
  PM --> RUN[auto-run L1]
  DEV --> RUN
  PIA --> RUN
```

| Timer | Actor | Rôle | Période |
|-------|-------|------|---------|
| `lbg-team-godot-supervisor-job` | `system:team_godot_supervisor` | qa (godot_supervisor) | **6 h** |
| `lbg-team-player-ia-job` | `system:team_player_ia` | player_ia probe | 12 h |
| `lbg-team-pm-reunification-job` | `system:team_pm_reunification` | pm brief | 24 h |
| `lbg-team-qa-smoke-job` | `system:team_qa_smoke` | qa smoke LAN | 24 h |

Installation :
```bash
bash infra/scripts/install_team_godot_supervisor_job_vm.sh
```

---

## Variables clés (`/etc/lbg-ia-mmo.env`)

```bash
LBG_TEAM_GODOT_SUPERVISOR_JOB_ENABLED=1
LBG_TEAM_GODOT_FOLLOWUP_ENABLED=1
LBG_TEAM_GODOT_FOLLOWUP_AUTO_RUN=1          # pm + dev_game + player_ia auto
LBG_CORE3_SIDECAR_URL=http://192.168.0.246:8791
LBG_TEAM_GODOT_GATEWAY_SMOKE=0              # 1 quand gateway :50000 actif sur 246
LBG_TEAM_GODOT_GATEWAY_HOST=192.168.0.246
LBG_GATEWAY_WS2_PREVIEW=1                   # négociation lbg-ws/2 sur gateway
```

---

## Pilot `#/team` — raccourcis

| Bouton | Effet |
|--------|--------|
| **Supervise Godot** | qa godot_supervisor full → Lancer |
| **Audit lbg-ws/2** | dev_game piste gateway → Lancer |
| **Brief réunification** | pm sous-projets |
| **Sonde joueurs IA** | player_ia probe |

Plan NL exemple : *« supervise godot et lbg-ws/2 sur Prime »* → propose qa + dev_game.

---

## Pistes parallèles

### M1 — Prime 2D (`new_mmo/prime-client`)
- Miroir : `client-prime-lbg/run_sidecar_mirror.sh`
- Smoke : `infra/scripts/smoke_godot_sidecar_mirror_lan.sh`

### lbg-ws/2 — Gateway preview (`services/lbg_gateway/`)
- Client WS `proto: "lbg-ws/2"` → messages `zone_state` v2 (lecture snapshots)
- Audit équipe : tâche dev_game `godot_track: lbg_ws2`
- Spec C++ : `docs/core3_zone_bridge_spec.md` (ZB-0 à venir)

---

## Demain matin (checklist ops)

1. `systemctl list-timers 'lbg-team-*'` sur **140** — tous **active**
2. `#/team` filtrer `system:team_godot_supervisor` — dernière tâche **done**
3. Si **failed** : followups pm/dev_game/player_ia déjà **done** (auto-run)
4. Godot visuel (poste dev) : `run_sidecar_mirror.sh` + `godot4 --path prime-client`

---

## Références

- [`jalon_client_godot_sidecar_246.md`](jalon_client_godot_sidecar_246.md)
- [`runbook_promotion_prototype_core3.md`](runbook_promotion_prototype_core3.md)
- [`core3_zone_bridge_spec.md`](core3_zone_bridge_spec.md)
