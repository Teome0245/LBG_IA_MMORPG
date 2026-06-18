# Changelog — Split Prime / PreCU (juin 2026)

## Architecture cible

| VM | IP | Rôle | Binaire | Login UDP | Galaxie | MariaDB |
|----|-----|------|---------|-----------|---------|---------|
| **245** | 192.168.0.245 | PreCU seul + ops | `core3-swgemu` | 44453 | 2 | **locale** |
| **246** | 192.168.0.246 | Prime seul + IA | `core3-clean` | 44553 | 3 | **locale** (split MySQL) |

## Changements appliqués

### Infra / scripts

- `infra/scripts/split_prime_246_precu_245_vm.sh` — migration one-shot
- `infra/scripts/truncate_core3_logs_vm.sh` — vidage logs (74 Go libérés sur 245)
- `infra/scripts/install_core3_logrotate_vm.sh` — rotation `/tmp/core3-*.log`
- `infra/scripts/enable_core3_coredump_vm.sh both` — coredumps Prime + PreCU
- `infra/scripts/install_proxmox_guest_agent_vm.sh` — agent Proxmox sur 246
- SQL : `core3-galaxy-prime-lan246.sql`, `core3-galaxy-precu-lan245.sql`

### Code Lua (Prime)

- `ia_bridge_screenplay.lua` : fix cell cantina (`rosterCantinaCell`) + debounce téléport (anti-spam log)

### Launcher client

- `new_mmo/launchpad/launchpad.config.json` v2.0.3
- `infra/scripts/deploy_client_new_pc.ps1` — IPs inversées
- `docs/client_dual_launchpad.md` — schéma à jour

### UI admin comptes (`:8792` sur **245**)

- Reste sur **245** (MariaDB locale)
- Sonde PreCU en local (`127.0.0.1`), Prime via SSH sur **246**
- Affichage **IP client** + statut + port login dans la barre serveurs
- `infra/systemd/lbg-core3-account-admin.service`

### Agents / inventaire réseau

- `remote_targets.py` : `245` → precu, `246` → mmo/prime

## Déploiement post-split (2026-06-11)

| Action | Statut |
|--------|--------|
| UI admin `:8792` sur 245 (systemd + `/etc/lbg-core3-account-admin.env`) | **OK** — `active` |
| API `/api/servers` : IP client + statut + port | **OK** — PreCU `192.168.0.245:44453`, Prime `192.168.0.246:44553` |
| Launchpad `launchpad.config.json` v2.0.3 (source + `dist/win-unpacked`) | **OK** |
| `qemu-guest-agent` sur 246 | **OK** — `active` (remontée IP Proxmox) |
| Reboot complet 246 | **OK** — Prime `READY` après ~2 min |
| RAM 246 post-reboot | **7,8 Go** visibles dans la VM — si +4 Go attendus côté Proxmox, vérifier la taille mémoire dans l’hyperviseur puis redémarrer à nouveau |
| Services IA sur **246** (sidecar `:8791`, bots Lia/Nix) | **OK** — `lbg-core3-ia-sidecar`, `lbg-core3-ia-bot-client`, `lbg-core3-ia-bot-client-nix` actifs |
| UI admin comptes `:8792` | Reste sur **245** (MariaDB locale) — pas sur 246 |

### Correctifs infra

- `start_core3_account_admin_vm.sh` : rsync séparé (code vs unit systemd) + setup distant via `remote_setup_account_admin.sh` (stdin fiable)
- Token LAN obligatoire : `CORE3_ADMIN_TOKEN` dans `/etc/lbg-core3-account-admin.env`

## Split MySQL Prime (2026-06-17)

| Action | Statut |
|--------|--------|
| `split_mysql_prime_246_vm.sh` — MariaDB locale 246 | **OK** |
| `config-local.lua` → `DBHost = 127.0.0.1` | **OK** |
| Galaxie 3 seule sur 246 (Teome, Bot_IA*) | **OK** |
| Galaxie 3 retirée de 245 (PreCU seul) | **OK** |
| Test indépendance (Prime sans MySQL 245) | **OK** |

Script : `infra/scripts/split_mysql_prime_246_vm.sh`


```bash
# Redéployer l'UI admin
bash infra/scripts/start_core3_account_admin_vm.sh

# État serveurs (API launchpad)
curl -s http://192.168.0.245:8792/api/servers | jq

# Re-sync Prime Lua
LBG_NEW_MMO_VM_HOST=192.168.0.246 bash infra/scripts/deploy_core3_ia_bridge_vm.sh --restart

# Agent Proxmox + reboot 246 (RAM)
bash infra/scripts/install_proxmox_guest_agent_vm.sh 192.168.0.246
ssh lbg@192.168.0.246 'sudo reboot'
```

## Client SWG

| Profil | IP | Port |
|--------|-----|------|
| PreCU | 192.168.0.245 | 44453 |
| Prime | 192.168.0.246 | 44553 |

Status API launchpad : `http://192.168.0.245:8792/api/servers`
