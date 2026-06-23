# Runbook — stockage Proxmox et VM Prime (246)

Incident documenté : **2026-06-22** — VM **Prime** (`246`) en `running (io-error)` après saturation du pool LVM thin **`local-lvm`**.

## Symptômes

| Où | Signe |
|----|--------|
| Proxmox UI | Statut VM **246** : `running (io-error)` ; triangle jaune |
| Proxmox Summary | « L'agent invité n'est pas en service » |
| Graphiques | Chute brutale RAM / I/O ; VM injoignable en SSH |
| Poste dev | `ping 192.168.0.246` → *Destination Host Unreachable* |

**Cause racine** : le pool thin `pve/data` (`local-lvm`) était à **100 %** — plus aucun bloc physique pour les écritures des disques VM (dont `vm-246-disk-0`, 80 Go thin).

Déclencheur fréquent sur Prime : **build Antigravity** (`cmake --build` sous `/opt/lbg-antigravity/lbg-mmo/build`, journal `/tmp/core3-antigravity-build.log` pouvant dépasser des centaines de Mo).

## Architecture (nœud `192.168.0.201`)

Les VM **110** (front/ollama), **245** (precu/db) et **246** (mmo/prime) sont hébergées sur le second hyperviseur Proxmox à l'adresse **`192.168.0.201`**. La VM **140** (core-orchestrateur) reste hébergée sur le premier nœud **`192.168.0.200`**.

| Élément | Détail |
|---------|--------|
| Hyperviseurs | `192.168.0.200` (proxmox-1) et `192.168.0.201` (proxmox-2) |
| VM 246 Prime | disque `scsi0: local-lvm:vm-246-disk-0`, 80 Go thin, 12 Go RAM (sur proxmox-2) |
| Pool partagé | Les VM de chaque nœud partagent le pool `pve/data` de leur hyperviseur |
| Sur-provisionnement | Somme des disques thin > taille physique du pool (normal en thin) |

Le disque **guest** Ubuntu peut afficher 50 %+ libre (`df -h /`) alors que Proxmox est en **io-error** : c'est le pool **hyperviseur** qui est plein, pas seulement la partition vue dans la VM.

## Prévention

### 1. Sonde avant gros build ou chaque semaine

```bash
cd LBG_IA_MMO
bash infra/scripts/check_proxmox_storage_lan.sh
bash infra/scripts/check_proxmox_storage_lan.sh --json
```

Seuils par défaut : **warn ≥ 85 %**, **critical ≥ 95 %** sur `pve/data` (`LBG_PROXMOX_THIN_WARN_PCT`, `LBG_PROXMOX_THIN_CRIT_PCT`).

**Avant** un build C++ sur 246 :

```bash
bash infra/scripts/check_proxmox_storage_lan.sh || echo "NE PAS LANCER LE BUILD — libérer de l'espace"
LBG_NEW_MMO_VM_HOST=192.168.0.246 bash infra/scripts/build_core3_antigravity_vm.sh --sync
```

### 2. Hygiène disque sur Prime (après build)

```bash
bash infra/scripts/prime_disk_hygiene_vm.sh
# ou sur la VM :
bash infra/scripts/prime_disk_hygiene_vm.sh --remote-only
```

Supprime notamment :

- `/opt/lbg-antigravity/lbg-mmo/build` (artefacts CMake, régénérable)
- tronque `/tmp/core3-antigravity-build.log`

### 3. Auto-extension du pool thin (Proxmox, une fois)

Sur l'hôte Proxmox (`root@192.168.0.201`) :

```bash
# Étendre manuellement si du PFree existe sur le VG (ex. +16 Go)
lvextend -l +100%FREE pve/data
lvs -o lv_name,data_percent pve/data
```

Activer l'extension automatique (recommandé) dans `/etc/lvm/lvm.conf` :

```ini
activation {
    thin_pool_autoextend_threshold = 80
    thin_pool_autoextend_percent = 20
}
```

Puis `update-initramfs -u` si demandé et surveiller après montée en charge.

### 4. qemu-guest-agent sur Prime

Permet IP / arrêt propre dans Proxmox :

```bash
bash infra/scripts/install_proxmox_guest_agent_vm.sh 192.168.0.246
```

Dans Proxmox : VM 246 → Options → **QEMU Guest Agent** = activé (déjà le cas si `agent: 1` dans `qm config`).

### 5. Règles d'exploitation

- Ne pas enchaîner plusieurs builds complets sans `prime_disk_hygiene_vm.sh`.
- Surveiller aussi **VM 140** (`vm-140-disk-0` a déjà atteint 100 % data% lors de l'incident).
- Prévoir à moyen terme : 2ᵉ datastore, réduction taille disques thin, ou déplacement du build Antigravity hors du disque système Prime.

## Récupération (io-error)

### Étape A — Libérer le pool hyperviseur

```bash
ssh root@192.168.0.201
pvesm status
lvs -o lv_name,data_percent pve/data
# Si PFree > 0 sur le VG :
lvextend -l +100%FREE pve/data
```

Objectif : `data` **< 90 %**.

### Étape B — Redémarrer Prime

L'agent invité est souvent absent quand le guest est figé :

```bash
qm status 246
qm stop 246 --skiplock    # shutdown propre échoue sans guest-agent
qm start 246
qm status 246             # doit être "running" sans "io-error"
```

### Étape C — Vérifier les services

```bash
ssh lbg@192.168.0.246
df -h /
systemctl is-active lbg-core3-prime.service
curl -s http://127.0.0.1:8791/healthz
bash infra/scripts/prime_disk_hygiene_vm.sh --remote-only
```

### Étape D — Contrôle depuis le poste dev

```bash
bash infra/scripts/check_proxmox_storage_lan.sh
ping -c 2 192.168.0.246
bash infra/scripts/smoke_core3_prime_world_lan.sh
```

## Intégration watchdog et Pilot (#/jobs)

### Sonde manuelle / CI

```bash
bash infra/scripts/check_proxmox_storage_lan.sh --json
```

### Timer VM core 140 → jobs Pilot

Sur **192.168.0.140**, le timer `lbg-storage-watchdog-job` (toutes les **10 min**) :

1. Sonde SSH Proxmox (`pve/data`, statut VM 246)
2. Si pool ≥ **85 %** (warn) ou ≥ **95 %** (critical) → crée un job orchestrateur
3. Job visible dans Pilot : [http://192.168.0.110:8080/#/jobs](http://192.168.0.110:8080/#/jobs) (filtrer `system:storage_watchdog`)

Installation :

```bash
bash infra/scripts/install_storage_watchdog_job_vm.sh
```

**Prérequis** : la clé SSH de `lbg@140` doit être autorisée sur `root@192.168.0.201` (sonde `lvs` / `qm status`) :

```bash
PUB=$(ssh lbg@192.168.0.140 'cat ~/.ssh/id_ed25519.pub')
ssh root@192.168.0.201 "grep -qF \"$PUB\" ~/.ssh/authorized_keys || echo \"$PUB\" >> ~/.ssh/authorized_keys"
```

Test manuel :

```bash
ssh lbg@192.168.0.140 'sudo systemctl start lbg-storage-watchdog-job.service && journalctl -u lbg-storage-watchdog-job -n 30 --no-pager'
```

Chaque job exécute (via planner) :

| Étape | Action |
|-------|--------|
| 1 | `proxmox_storage` — sonde pool thin |
| 2 | `storage_remediation_plan` — hygiène Prime SSH, lvextend, restart si io-error |
| 3 | Synthèse dialogue — résumé français pour l'opérateur |

**Approbation apply** : pour l'hygiène disque Prime (`rm -rf .../build`), activer `LBG_JOBS_RUNNER_ENABLED=1` et fournir `LBG_JOBS_APPROVAL_TOKEN` ; la commande doit être dans `LBG_SSH_CMD_ALLOWLIST`.

Cooldown entre jobs : **30 min** (warn) / **15 min** (critical) — variables `LBG_STORAGE_WATCHDOG_COOLDOWN_*`.

Le watchdog infra général (`lbg-infra-watchdog`, 5 min) inclut aussi la sonde stockage dans son agrégat.

Référence ops : [`runbook_ops_bots_watchdog.md`](runbook_ops_bots_watchdog.md).

## Références

- [`core3_prime_runbook.md`](core3_prime_runbook.md) — déploiement Prime
- [`infra/scripts/build_core3_antigravity_vm.sh`](../infra/scripts/build_core3_antigravity_vm.sh)
- [`infra/scripts/install_proxmox_guest_agent_vm.sh`](../infra/scripts/install_proxmox_guest_agent_vm.sh)
- Incident : build `core3-clean` juin 2026, pool `local-lvm` 100 %, extension `lvextend` +16 Go, redémarrage 246
