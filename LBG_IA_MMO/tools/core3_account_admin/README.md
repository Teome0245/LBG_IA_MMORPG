# Core3 Account Admin (UI web)

Interface web minimale pour gérer les comptes MariaDB **`swgemu`** (Core3 / SWGEmu).

## Fonctions

- Lister les comptes (admin level, actif, nombre de persos)
- Créer un compte (hash mot de passe compatible Core3)
- Modifier `admin_level`, `active`, mot de passe
- Supprimer un compte (sessions, bans, personnages, etc.)
- Voir les personnages liés

## Prérequis

```bash
pip install -r requirements.txt
```

## Variables d'environnement

| Variable | Défaut | Description |
|----------|--------|-------------|
| `CORE3_DB_HOST` | `127.0.0.1` | Hôte MariaDB |
| `CORE3_DB_PORT` | `3306` | Port |
| `CORE3_DB_USER` | `swgemu` | Utilisateur |
| `CORE3_DB_PASS` | *(vide)* | Mot de passe DB |
| `CORE3_DB_NAME` | `swgemu` | Base |
| `CORE3_DB_SECRET` | `swgemus3cr37!` | `DBSecret` du `config.lua` Core3 |
| `CORE3_ADMIN_BIND` | `127.0.0.1:8792` | Adresse d'écoute |
| `CORE3_PRECU_STATUS_HOST` | `127.0.0.1` | SSH sonde PreCU (local sur 245) |
| `CORE3_PRECU_CLIENT_IP` | `192.168.0.245` | IP affichée / client SWG PreCU |
| `CORE3_PRIME_STATUS_HOST` | `192.168.0.246` | SSH sonde Prime (VM 246) |
| `CORE3_PRIME_CLIENT_IP` | `192.168.0.246` | IP affichée / client SWG Prime |
| `CORE3_ADMIN_TOKEN` | *(vide)* | Token obligatoire si écoute LAN |

## Lancement (VM 245)

```bash
export CORE3_DB_PASS='123456'
export CORE3_DB_SECRET='swgemus3cr37!'
export CORE3_ADMIN_TOKEN='changez-moi'
export CORE3_ADMIN_BIND='192.168.0.245:8792'

python3 core3_account_admin.py
```

Ouvrir : `http://192.168.0.245:8792/` — renseigner le token dans l'en-tête de la page.

## Sécurité

- Par défaut : écoute **localhost** uniquement.
- Sur le LAN : **toujours** définir `CORE3_ADMIN_TOKEN` (sinon le programme refuse de démarrer).
- Ne pas exposer ce port sur Internet sans reverse-proxy + TLS.

## Script VM

`LBG_IA_MMO/infra/scripts/start_core3_account_admin_vm.sh`
