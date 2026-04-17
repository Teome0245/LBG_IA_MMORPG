# VM — compte dédié `lbg` (sudoer + services)

Objectif : ne plus utiliser un compte personnel pour le déploiement et l’exécution des services **LBG_IA_MMO** sur la VM. Le compte Unix **`lbg`** :

- se connecte en **SSH** pour `deploy_vm.sh` / `push_secrets_vm.sh` ;
- est **membre de `sudo`** pour les opérations privilégiées (rsync vers `/opt`, `systemctl`, `logrotate`, etc.) ;
- est le **propriétaire** de `/opt/LBG_IA_MMO` et du **venv** ;
- est l’utilisateur des **unités systemd** `lbg-*.service` (`User=lbg` / `Group=lbg`).

## 1. Création du compte (une fois par VM)

En **root** ou via un admin déjà sudo sur la machine :

```bash
sudo adduser --disabled-password --gecos "LBG IA MMO" lbg
sudo usermod -aG sudo lbg
```

Clé SSH (depuis le poste de dev) :

```bash
sudo install -d -m 700 -o lbg -g lbg /home/lbg/.ssh
# Coller la clé publique :
sudo nano /home/lbg/.ssh/authorized_keys
sudo chmod 600 /home/lbg/.ssh/authorized_keys
sudo chown lbg:lbg /home/lbg/.ssh/authorized_keys
```

### Où renseigner le mot de passe de `lbg` ?

- **Uniquement sur la VM**, avec : `sudo passwd lbg` (compte root ou autre admin sudo).
- **Pas** dans `infra/secrets/lbg.env`, **pas** dans Git : ce fichier est pour les variables **`LBG_*`** (appli), pas pour l’authentification Unix.
- Avec `adduser --disabled-password`, la connexion SSH se fait surtout par **clé** ; le mot de passe sert surtout pour **`sudo`** (invite après `sudo -v` lors des scripts de déploiement) ou pour un accès console de secours.
- Alternative : règles **sudo NOPASSWD** ciblées (prod avancée) — hors dépôt.

## 2. Répertoire d’application et logs

Après la **première** promotion du code sous `/opt/LBG_IA_MMO` (ou migration depuis un ancien user) :

```bash
sudo chown -R lbg:lbg /opt/LBG_IA_MMO
sudo install -d -m 0755 -o lbg -g lbg /var/log/lbg
```

### Données persistantes MMO (optionnel)

Si tu utilises **`LBG_MMO_STATE_PATH=/var/lib/lbg/mmo/world_state.json`** (état `WorldState` hors de `/opt`), crée le répertoire une fois :

```bash
sudo install -d -m 0755 -o lbg -g lbg /var/lib/lbg/mmo
```

### Reset état `mmo_server` (recharger le seed)

Le `mmo_server` persiste son `WorldState` et, **à l’arrêt**, effectue une sauvegarde finale.
Conséquence : un simple `sudo systemctl restart lbg-mmo-server` peut :

- arrêter le service,
- **sauvegarder** l’état courant à l’arrêt (recréant le fichier `world_state.json`),
- puis redémarrer,

ce qui empêche le rechargement du seed si tu voulais repartir “à blanc”.

Procédure recommandée (LAN) : **stop → déplacer le state → start**.
Script fourni (depuis le poste de dev) :

```bash
cd LBG_IA_MMO
LBG_VM_HOST=192.168.0.245 LBG_VM_USER=lbg bash infra/scripts/reset_mmo_state_vm.sh
```

Option : si tu as externalisé l’état (ex. `/var/lib/lbg/mmo/world_state.json`), tu peux cibler le fichier :

```bash
cd LBG_IA_MMO
LBG_VM_HOST=192.168.0.245 LBG_VM_USER=lbg LBG_MMO_STATE_PATH="/var/lib/lbg/mmo/world_state.json" \
  bash infra/scripts/reset_mmo_state_vm.sh
```

## 3. Fichier d’environnement `/etc/lbg-ia-mmo.env`

Les services tournent sous **`lbg`** : le fichier doit être lisible par ce groupe, **sans** être lisible par « others ».

```bash
sudo chgrp lbg /etc/lbg-ia-mmo.env
sudo chmod 640 /etc/lbg-ia-mmo.env
sudo chown root:lbg /etc/lbg-ia-mmo.env
```

`push_secrets_vm.sh` installe désormais ce mode par défaut (640, `root:lbg`). Si le groupe `lbg` n’existe pas encore, créer le user `lbg` **avant** le premier push.

Sans variable de cible, le script enchaîne les **trois** VM LAN (défauts `LBG_LAN_HOST_CORE` / `MMO` / `FRONT`, voir `docs/fusion_env_lan.md`) ; pour une seule machine : `LBG_VM_HOST=… bash infra/scripts/push_secrets_vm.sh`.

## 4. Déploiement depuis le poste de dev

Variables attendues (défauts dans les scripts : utilisateur **`lbg`**) :

```bash
export LBG_VM_HOST=192.168.0.140
export LBG_VM_USER=lbg
bash infra/scripts/deploy_vm.sh
```

Compte **service** (propriétaire de `/opt` et utilisateur systemd) : `LBG_VM_SERVICE_USER` (défaut **`lbg`**). À ne changer que si tu alignes aussi les unités systemd.

Ancien compte personnel encore utilisé : `LBG_VM_USER=ton_user` le temps de la migration, puis bascule vers `lbg`.

## 5. Vérifications

```bash
ssh lbg@<vm> 'id && groups'
ssh lbg@<vm> 'sudo -v && systemctl is-active lbg-orchestrator lbg-backend'
```

### Permission denied (publickey) — `deploy_vm.sh`, `smoke_vm_lan.sh`, `push_secrets_vm.sh`

Les scripts utilisent **`ssh lbg@<IP>`** (ou `LBG_VM_USER`). Tant que la **clé publique** de ton poste n’est pas dans **`/home/lbg/.ssh/authorized_keys`** sur **chaque** VM, tu obtiens cette erreur.

**Diagnostic** : si tu n’as **plus** `Load key … error in libcrypto`, la **clé privée** est bonne côté poste. Un **`Permission denied (publickey)`** signifie alors que le **serveur** n’a pas la **clé publique** correspondante pour ce compte (ou droits `authorized_keys` incorrects). Il faut **`ssh-copy-id`** ou copie manuelle du `.pub` — pas un autre fichier `id_ed25519` local.

**Option A — une fois par VM** (mot de passe `lbg` ou accès root/console si le compte n’a pas encore de clé) :

```bash
ssh-copy-id -i ~/.ssh/id_ed25519.pub lbg@192.168.0.140
ssh-copy-id -i ~/.ssh/id_ed25519.pub lbg@192.168.0.110
ssh-copy-id -i ~/.ssh/id_ed25519.pub lbg@192.168.0.245
```

Puis test sans mot de passe :

```bash
ssh -o BatchMode=yes lbg@192.168.0.140 true && echo OK
```

**Une seule VM refuse encore** (ex. **140** et **110** OK, **245** seule en échec) : la clé n’est pas encore côté `lbg` sur cette machine. Si **`ssh-copy-id`** échoue aussi (**Permission denied**), tu n’as pas d’entrée SSH pour `lbg` sur cet hôte — se connecter avec **un autre compte** qui marche (`ssh autre@192.168.0.245`), puis en **sudo** : créer `/home/lbg/.ssh/authorized_keys` et y coller **une ligne** de `~/.ssh/id_ed25519.pub` (voir § **1**). Sinon : **console** hyperviseur ou activer temporairement l’auth par mot de passe pour une première installation de clé.

**Option B —** tu te connectes déjà avec un **autre** compte (ex. personnel) dont la clé est acceptée : en attendant de copier la clé pour `lbg`, tu peux lancer les scripts avec  
`LBG_VM_USER=ton_user` (voir aussi `LBG_SSH_IDENTITY` dans l’en-tête de `infra/scripts/smoke_vm_lan.sh`).

**`LBG_SSH_IDENTITY`** doit pointer vers la **clé privée** (sans `.pub`), par ex. `~/.ssh/id_ed25519` ou `~/.ssh/id_rsa` — pas un nom inventé du type `ma_cle` si ce fichier n’existe pas.

**Astuce (poste de dev / WSL)** : pour éviter de répéter la variable à chaque commande, tu peux l’exporter une fois par shell (ou la mettre dans `~/.bashrc`) :

```bash
export LBG_SSH_IDENTITY="$HOME/.ssh/id_ed25519"
```

**`LBG_SSH_KNOWN_HOSTS_FILE`** (utilisé par `infra/scripts/smoke_vm_lan.sh`) : chemin vers un fichier `known_hosts` **écrivable** (ex. `/tmp/lbg_known_hosts`). Si absent, le script utilise un fichier temporaire. Utile si ton contexte d’exécution ne peut pas écrire dans `~/.ssh`.

**`Load key "...": error in libcrypto`** : le chemin ne désigne pas une clé privée valide (fichier absent, vide, corrompu, ou mauvais fichier). Vérifier : `ls -la ~/.ssh/` ; la première ligne du fichier doit ressembler à `-----BEGIN OPENSSH PRIVATE KEY-----` ou `-----BEGIN RSA PRIVATE KEY-----`.

**Option C —** coller la clé à la main : § **1** de ce document (`authorized_keys`, droits `600`).

## 6. Références

- `infra/systemd/lbg-*.service` — `User=lbg` / `Group=lbg`
- `infra/scripts/deploy_vm.sh` — `chown` + `install_local` en tant que `lbg`
- `infra/scripts/push_secrets_vm.sh` — droits `640 root:lbg`
- `infra/logrotate/lbg-devops-audit` — `create 0640 lbg lbg`
- `docs/ops_devops_audit.md` — audit JSONL
