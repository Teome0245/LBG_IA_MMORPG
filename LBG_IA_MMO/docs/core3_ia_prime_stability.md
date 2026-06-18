# Stabilité — Serveur Prime (core3-clean, VM **246**)

> **Architecture (juin 2026)** : Prime seul sur **192.168.0.246** ; PreCU seul sur **192.168.0.245** (MariaDB locale). Script : `infra/scripts/split_prime_246_precu_245_vm.sh`

## Symptômes courants

| Perçu | Cause réelle |
|-------|----------------|
| Launchpad « hors ligne » | Boot Core3 ~2–3 min + `RestartSec=45` après crash |
| « Le serveur coupe tout le temps » | Mélange deploy `--restart` **et** crashs natifs |
| PNJ `[IA]` immobile | `roam_mode: linger` (volontaire, anti-murs) — voir `walk_patrol` |

## Crashs (journal systemd)

```bash
ssh lbg@192.168.0.245 'sudo journalctl -u lbg-core3-prime.service --since today | grep -E "SEGV|Stopped|Started"'
```

**2026-05-24** : 3× `status=11/SEGV` (~10–25 min d’uptime). Souvent pendant `ObjectManager` / backup BDD ; un cas après `GetAttributesBatchCommand` >1000 objets (compte **Teome**, god mode + inspect massif).

Pas d’OOM observé (~5 Go RSS, pas de `oom-kill` noyau).

## Berkeley DB — `BDB0060` / `DatabaseException`

Symptômes dans `/tmp/core3-clean.log` :

```text
(BDB0060 PANIC: fatal region error detected; run recovery
terminate called after throwing an instance of 'engine::db::DatabaseException'
```

**Cause fréquente** : arrêt brutal (`kill -9`, coupure VM, deux `core3-clean` sur le même `databases/`, install binaire pendant que le serveur tournait encore).

**Répertoire concerné (Prime uniquement)** :

```text
/opt/lbg-new-mmo-clean/MMOCoreORB/bin/databases/
```

Ne **jamais** rsync ce dossier depuis le poste de dev ni depuis l’instance Pre-CU (`/opt/lbg-new-mmo/MMOCoreORB/bin/databases/`).

### Procédure recovery (VM 245)

Depuis le poste de dev :

```bash
bash infra/scripts/recover_core3_clean_bdb_vm.sh
```

Ou manuellement sur la VM :

```bash
BIN=/opt/lbg-new-mmo-clean/MMOCoreORB/bin
DB="${BIN}/databases"

# 1) Arrêt propre (obligatoire)
sudo systemctl stop lbg-core3-prime.service
pkill -x core3-clean 2>/dev/null || true
sleep 3
pgrep -x core3-clean && echo "encore actif — ne pas lancer db_recover" && exit 1

# 2) Backup horodaté
ts=$(date +%Y%m%d_%H%M%S)
cp -a "${DB}" "${BIN}/databases.bak.${ts}"

# 3) Recovery Berkeley DB 5.3
cd "${DB}"
db_recover -h . -v
db_verify -V

# 4) Redémarrage
sudo systemctl start lbg-core3-prime.service
tail -f /tmp/core3-clean.log   # attendre [Core] initialized puis READY (~2–3 min)
```

**Vérification** :

```bash
pgrep -a core3-clean
ss -ulnp | grep -E '44553|44563'    # login + zone Prime
grep -E 'READY|BDB0060|DatabaseException' /tmp/core3-clean.log | tail -5
```

### Si `db_recover` échoue ou boucle de crash

1. Restaurer le backup le plus récent :  
   `rm -rf databases && cp -a databases.bak.YYYYMMDD_HHMMSS databases`
2. En dernier recours (perte persistance objets monde, comptes MariaDB inchangés) :  
   arrêter le serveur, renommer `databases` → `databases.corrupt.TIMESTAMP`,  
   `mkdir databases`, redémarrer (Core3 recrée des `.db` vides au boot).

### Après install binaire (`install_core3_clean_after_vm_build.sh`)

Le script fait `pkill core3-clean` puis `nohup` — si systemd `lbg-core3-prime` est **active**, préférer :

```bash
bash infra/scripts/install_core3_clean_after_vm_build.sh
bash infra/scripts/restart_core3_prime_vm.sh   # un seul superviseur
```

Évite un double démarrage (nohup + systemd) sur les mêmes fichiers BDB.

## Redémarrages attendus (ops)

- `bash infra/scripts/deploy_core3_ia_bridge_vm.sh --restart`
- `bash infra/scripts/restart_core3_prime_vm.sh`

Préférer `--no-restart` si seul le sidecar / JSON catalogue change.

## Core dumps

```bash
bash infra/scripts/enable_core3_coredump_vm.sh
```

Après un SEGV sur la VM :

```bash
coredumpctl list | grep core3
coredumpctl info core3-clean
coredumpctl gdb core3-clean   # bt full
```

## Garde / Archiviste — déplacement

| Mode | Comportement |
|------|----------------|
| `linger` | Statique + animations (ancien défaut C.1) |
| `patrol` | `AI_PATROLLING` — **traverse les murs** en outdoor |
| `walk_patrol` | `setNextPosition` + `executeBehavior` + jalons `roam_patrol` |

Référence : `content/core3/lua/ia_bridge_screenplay.lua` (`npc:core3_guard`, `npc:core3_scribe`).

## Joueur god mode (Teome)

Éviter l’inspection batch de >1000 objets (client / `@objinfo` en masse) : le serveur logue une erreur et un SEGV a été observé juste après.

## Fichiers utiles

| Fichier | Rôle |
|---------|------|
| `/tmp/core3-clean.log` | Log applicatif (append) |
| `journalctl -u lbg-core3-prime.service` | Arrêts / SEGV / restart systemd |
| `infra/systemd/lbg-core3-prime.service` | Unité `Restart=always` |
