# Ops — bots-ensure (246) et watchdog infra (140)

Procédure reproductible pour stabiliser les joueurs IA et la sonde infra LAN.

## Prérequis

- Accès SSH `lbg@192.168.0.246` (Prime) et `lbg@192.168.0.140` (core)
- Repo déployé sous `/opt/LBG_IA_MMO` sur les VMs

## 1. Timer `lbg-core3-ia-bots-ensure` (VM 246)

Réconnecte Lia / Nix / Mira si hors ligne sans redémarrer Core3.

```bash
# Depuis poste dev (WSL)
cd LBG_IA_MMO
bash infra/scripts/install_core3_ia_bots_ensure_vm.sh
```

Sur la VM :

```bash
systemctl is-active lbg-core3-ia-bots-ensure.timer
systemctl list-timers | grep bots-ensure
sudo systemctl start lbg-core3-ia-bots-ensure.service   # test manuel
journalctl -u lbg-core3-ia-bots-ensure.service -n 30 --no-pager
```

Variables (`/etc/lbg-core3-ia.env` ou `lbg-ia-mmo.env`) :

| Variable | Défaut | Rôle |
|----------|--------|------|
| `LBG_CORE3_IA_SIDECAR_URL` | `http://127.0.0.1:8791` | Sidecar Prime |
| `LBG_CORE3_IA_BOTS` | `lia,nix,mira` | Comptes à assurer |
| `LBG_CORE3_BOT_RECONNECT_COOLDOWN_S` | `180` | Anti-spam reconnect |

## 2. Watchdog infra (VM 140)

Agrège Proxmox + sonde RAM VMs (Prime exclu par défaut pendant rebuild).

```bash
# Kind devops depuis orchestrateur ou script direct
PYTHONPATH=agents/src python3 -c "
from lbg_agents.infra_watchdog import run_infra_watchdog
import json; print(json.dumps(run_infra_watchdog(persist=False), indent=2))
"
```

Variables utiles :

| Variable | Rôle |
|----------|------|
| `LBG_INFRA_WATCHDOG_ENABLED` | `1` par défaut |
| `PROXMOX_HOST` / `PROXMOX_TOKEN` | Sonde cluster (read-only) |
| `LBG_VM_MEMORY_EXCLUDE_PRIME` | `1` = ne pas alerter sur 246 |

Installation timer (si unité présente dans repo) :

```bash
# À adapter selon unités infra/systemd/lbg-infra-watchdog.*
sudo systemctl enable --now lbg-infra-watchdog.timer
```

## 3. Validation rapide

```bash
curl -s http://192.168.0.246:8791/healthz
curl -s "http://192.168.0.246:8791/v1/player-snapshot?player=Lia" | head -c 400
```

## 4. Lost Heaven redirect

Redirect login ME → hub désert **désactivé** (`IA_BRIDGE_LOST_HEAVEN_ENABLED = false`).  
Redéployer Lua après changement :

```bash
bash infra/scripts/deploy_core3_ia_bridge_vm.sh --restart
```

Voir [`scrapaltai_starting_locations_mod.md`](scrapaltai_starting_locations_mod.md).

## Références

- `infra/systemd/lbg-core3-ia-bots-ensure.service`
- `agents/src/lbg_agents/infra_watchdog.py`
- [`plan_parallel_next_steps.md`](plan_parallel_next_steps.md) — Track G
