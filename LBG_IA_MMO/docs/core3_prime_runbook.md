# Runbook — Prime Core3 (systèmes monde)

Guide opérationnel unique : déploiement, validation, commandes `pending.jsonl`.

## Prérequis

- VM Prime : `192.168.0.246` (`LBG_PRIME_VM_HOST` / `LBG_NEW_MMO_VM_HOST`)
- VM PreCU : `192.168.0.245` (`LBG_PRECU_VM_HOST`) — MariaDB locale
- Split : `bash infra/scripts/split_prime_246_precu_245_vm.sh`
- Binaire : `/opt/lbg-new-mmo-clean/MMOCoreORB/bin/core3-clean`
- Lia (`Bot_IA`) connectée sur **galaxie 3** / Tatooine pour smokes snapshot
- Sidecar IA : `http://127.0.0.1:8791` sur la VM

## 1. Déploiement (ordre)

```bash
cd LBG_IA_MMO

# Stockage Proxmox (éviter io-error sur 246) — avant gros build
bash infra/scripts/check_proxmox_storage_lan.sh

# Lua + JSON (sans rebuild C++)
bash infra/scripts/deploy_core3_ia_bridge_vm.sh --restart

# APIs C++ GameTime / EventBus (si modifs DirectorManager)
bash infra/scripts/build_core3_antigravity_vm.sh --sync
bash infra/scripts/install_core3_clean_after_vm_build.sh
bash infra/scripts/restart_core3_prime_vm.sh

# Après build : libérer artefacts sur Prime
bash infra/scripts/prime_disk_hygiene_vm.sh
```

Voir [`runbook_proxmox_storage_prime.md`](runbook_proxmox_storage_prime.md) si statut VM `io-error`.

## 2. Smoke automatisé

```bash
bash infra/scripts/smoke_core3_prime_world_lan.sh
bash infra/scripts/smoke_core3_prime_world_lan.sh --with-think
bash infra/scripts/smoke_core3_prime_world_lan.sh --demo-pending
```

`--demo-pending` envoie la séquence quêtes / commerce / craft / housing sur la VM.

## 3. Format `pending.jsonl`

Une ligne = une commande :

```text
action|player|zone|x|y|z|message
```

| Action | Exemple |
|--------|---------|
| `npc_say` | `npc_say\|npc:core3_scribe\|tatooine\|0\|0\|0\|Bonjour.` |
| `offer_quest` | `offer_quest\|npc:core3_vex_sorn\|tatooine\|0\|0\|0\|Teome\|quest:mos_delivery_water` |
| `interact` | `interact\|Lia\|tatooine\|0\|0\|0\|quest_accept:Teome:quest:mos_delivery_water` |
| `vendor_buy` | `vendor_buy\|npc:core3_scribe\|tatooine\|0\|0\|0\|Teome\|0` |
| `craft_combine` | `craft_combine\|Lia\|tatooine\|0\|0\|0\|craft:mos_ration_pack` |
| `housing_enter` | `housing_enter\|Lia\|tatooine\|0\|0\|0\|` |

Fichier VM : `/opt/lbg-new-mmo-clean/MMOCoreORB/bin/ia_bridge/pending.jsonl`

## 4. Fichiers de preuve (VM)

| Fichier | Contenu |
|---------|---------|
| `ia_bridge/quest_state.jsonl` | offres / accept / turn-in |
| `ia_bridge/events.jsonl` | événements sociaux |
| `ia_bridge/world_events.jsonl` | bus C++ (après rebuild) |
| `ia_bridge/npc_passive_state.json` | tick simulation passive |
| `ia_bridge/npc_snapshots.json` | positions PNJ pilotes |
| `/tmp/core3-clean.log` | log serveur (nohup) |

## 5. Smokes historiques (phases B–D)

Toujours utiles pour régression IA bridge :

```bash
bash infra/scripts/smoke_core3_ia_phase_b_lan.sh --with-think
bash infra/scripts/smoke_core3_ia_phase_c_lan.sh --with-think
bash infra/scripts/smoke_core3_ia_phase_c4b_game_time_lan.sh
bash infra/scripts/smoke_core3_ia_phase_c5_quest_giver_lan.sh --with-think
bash infra/scripts/smoke_core3_ia_phase_d_headless_bot_lan.sh
```

## 5bis. Endpoint snapshot (sidecar)

Le sidecar n’expose pas `/snapshot` : utiliser :

- `GET http://127.0.0.1:8791/v1/player-snapshot?player=Lia`

Réponses :

- `200` si `online=true`
- `409` si le joueur n’est pas considéré en ligne

## 6. Code C++ (new_mmo)

Modifs : `lbg-mmo/server-core3/server/zone/managers/director/DirectorManager.{h,cpp}`

Fonctions Lua : `iaConfigureGameTime`, `iaGetGameTime`, `iaGetDayPhase`, `iaPublishWorldEvent`, `iaPollWorldEvent`.

## 7. Housing / nage / vol

Étude : [`core3_housing_swim_flight_study.md`](core3_housing_swim_flight_study.md) — MVP housing = `housing_enter` uniquement.

## 8. Watchdog blocage login (uptime ~17 h)

Symptômes connus : `StreamIndexOutOfBoundsException` en rafale sur `handleNetStatusRequest`, headless `Login process timed out`, auth OK après `systemctl restart lbg-core3-prime`.

Timer **toutes les 5 min** sur la VM 245 :

```bash
bash infra/scripts/install_core3_prime_watchdog_vm.sh
bash infra/scripts/watch_core3_prime_login_health.sh --dry-run --json   # test sans restart
journalctl -u lbg-core3-prime-watchdog.service -n 30 --no-pager
systemctl list-timers lbg-core3-prime-watchdog.timer
```

Critères de restart (cooldown 45 min par défaut) :

- échec `core3client --login-only` (sonde auth headless) ;
- ≥ 4 `StreamIndexOutOfBoundsException` dans le tail de `log/core3.log` ;
- `Login process timed out` récent dans `log/core3client.log`.

Après restart : `post_prime_ia_bots.sh` (ExecStartPost) relance Lia/Nix.

Variables : `LBG_CORE3_PRIME_WATCHDOG_*` dans `/etc/lbg-ia-mmo.env`.

## 9. Berkeley DB (crash `BDB0060`)

Voir [`core3_ia_prime_stability.md`](core3_ia_prime_stability.md) — section Berkeley DB.

```bash
bash infra/scripts/recover_core3_clean_bdb_vm.sh
```
