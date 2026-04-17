# Opérations — audit DevOps & jeton d’approbation

Ce document complète `agents/README.md` (variables `LBG_DEVOPS_*`) pour la **prod** (VM systemd, réseau privé).

## Fichier d’audit JSONL (`LBG_DEVOPS_AUDIT_LOG_PATH`)

### Créer le répertoire et les droits

L’orchestrator doit pouvoir **écrire** dans le fichier (ouverture en append à chaque ligne, pas de descripteur gardé ouvert).

```bash
sudo install -d -m 0755 -o lbg -g lbg /var/log/lbg
```

Voir `docs/ops_vm_user.md` pour le compte **`lbg`** (sudoer + services systemd).

Dans `/etc/lbg-ia-mmo.env` (ou équivalent) :

```bash
LBG_DEVOPS_AUDIT_LOG_PATH="/var/log/lbg/devops_audit.jsonl"
```

Redémarrer l’orchestrator après modification :

```bash
sudo systemctl restart lbg-orchestrator
```

### Rotation avec logrotate

Fichier d’exemple dans le dépôt : `infra/logrotate/lbg-devops-audit`.

Installation sur la VM :

```bash
sudo cp /opt/LBG_IA_MMO/infra/logrotate/lbg-devops-audit /etc/logrotate.d/lbg-devops-audit
# Puis :
sudo logrotate -d /etc/logrotate.d/lbg-devops-audit
sudo logrotate -f /etc/logrotate.d/lbg-devops-audit   # test manuel optionnel
```

**Pourquoi pas `copytruncate` ?** Chaque écriture d’audit rouvre le fichier en mode append : après rotation (renommage du fichier courant + création d’un fichier vide), les nouvelles lignes vont dans le nouveau fichier sans signal `HUP`.

Vérifier la planification système (Debian/Ubuntu : tâche quotidienne `logrotate` via cron).

## Rotation du jeton `LBG_DEVOPS_APPROVAL_TOKEN`

### Règles

- Le jeton vit **uniquement** côté serveur (`/etc/lbg-ia-mmo.env` ou coffre secrets), **jamais** dans le dépôt Git.
- Une seule valeur est valide à la fois (pas de « double jeton » dans le code actuel) : la rotation est un **basculement net**.
- Tout client qui envoie `context.devops_approval` (ex. scripts CI, `/pilot/`) doit être mis à jour **après** le redémarrage qui charge le nouveau jeton.

### Procédure recommandée (fenêtre courte)

1. **Générer** un nouveau secret (long, aléatoire), ex. :
   ```bash
   openssl rand -hex 32
   ```
2. **Mettre à jour** `LBG_DEVOPS_APPROVAL_TOKEN` dans `/etc/lbg-ia-mmo.env` sur la VM (ou repousser via `infra/scripts/push_secrets_vm.sh` si c’est votre flux).
3. **Redémarrer** l’orchestrator :
   ```bash
   sudo systemctl restart lbg-orchestrator
   ```
4. **Mettre à jour** les appelants (variables d’environnement CI, champs saisis dans `/pilot/`, etc.) avec la **nouvelle** valeur.
5. **Révoquer** l’ancien jeton : une fois l’étape 4 faite pour tous les acteurs, l’ancienne valeur ne sert plus ; ne la conservez pas dans des historiques de shell ou captures d’écran.

### Urgence / compromission

En cas de fuite supposée du jeton : générer un nouveau jeton immédiatement, appliquer les étapes 2–3, puis invalider tous les usages de l’ancien (même ordre si vous acceptez quelques minutes où les anciens scripts échouent jusqu’à mise à jour).

### Audit

Les lignes `agents.devops.audit` (fichier JSONL et/ou journald) permettent de corréler `trace_id` / `actor_id` / `outcome` (`approval_denied`, etc.) après un changement de politique — **sans** jamais logger la valeur de `devops_approval`.

## Références

- `agents/README.md` — tableau des variables DevOps
- `docs/ops_vm_user.md` — compte **`lbg`** (sudoer, SSH, propriétaire `/opt`, `User=` systemd)
- `infra/secrets/lbg.env.example` — exemples commentés
- `bootstrap.md` — déploiement VM et services systemd
