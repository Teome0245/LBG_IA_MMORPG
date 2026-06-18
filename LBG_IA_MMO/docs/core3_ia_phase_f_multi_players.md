# Phase F — Multi-joueurs IA (Lia + Nix)

**Statut** : préparation installée (VM 245), activation Nix en attente du mot de passe `Bot_IA_2`.

## Objectif

Piloter plusieurs personnages joueurs IA sur Serveur Prime :

| Joueur IA | Compte | Personnage | Rôle courant | Actor ID |
|-----------|--------|------------|--------------|----------|
| Lia | `Bot_IA` | `Lia Bot` | incarnation orchestrateur | `orchestrator:lia` |
| Nix | `Bot_IA_2` | `Nix Bot` | scout terrain | `orchestrator:nix` |

Les métiers SWG ne sont pas fixes : `profession_current` décrit l'état courant, et `profession_dynamic=true` signale que le persona doit s'adapter si le joueur change de métier.

## Fichiers ajoutés

| Fichier | Rôle |
|---------|------|
| `content/core3/core3_ia_players.json` | Registre Lia/Nix |
| `content/core3/ia_bridge/nix_bot_session.json` | Session headless Nix (`characterOid=281474995767993`) |
| `content/core3/nix_scout_persona.json` | Persona scout dynamique |
| `infra/snippets/.env-core3client-nix.example` | Env login Nix (mot de passe à renseigner) |
| `infra/systemd/lbg-core3-ia-bot-client-nix.service` | Service headless Nix |
| `infra/scripts/install_core3_ia_bot_client_nix_vm.sh` | Installation VM 245 |

## Installation réalisée

```bash
bash infra/scripts/install_core3_ia_bot_client_nix_vm.sh
```

Sur la VM 245 :

- `/opt/lbg-new-mmo-clean/MMOCoreORB/bin/ia_bridge/nix_bot_session.json`
- `/opt/lbg-new-mmo-clean/MMOCoreORB/bin/.env-core3client-nix`
- `/etc/systemd/system/lbg-core3-ia-bot-client-nix.service`

Le service n'est pas activé tant que `.env-core3client-nix` contient `CHANGE_ME_BOT_IA_2`.

## Activation Nix

Renseigner le mot de passe réel sur la VM 245 :

```bash
ssh lbg@192.168.0.245
nano /opt/lbg-new-mmo-clean/MMOCoreORB/bin/.env-core3client-nix
chmod 600 /opt/lbg-new-mmo-clean/MMOCoreORB/bin/.env-core3client-nix
```

Tester le login :

```bash
CORE3_IA_BOT_CHARACTER=Nix \
CORE3_CLIENT_ENV_FILE=/opt/lbg-new-mmo-clean/MMOCoreORB/bin/.env-core3client-nix \
CORE3_CLIENT_OPTIONS_JSON=/opt/lbg-new-mmo-clean/MMOCoreORB/bin/ia_bridge/nix_bot_session.json \
bash /opt/LBG_IA_MMO/infra/scripts/run_core3_ia_bot_client_vm.sh --login-only
```

Activer ensuite :

```bash
sudo systemctl enable --now lbg-core3-ia-bot-client-nix
```

## Pilotage manuel

Une fois Nix connecté :

```bash
curl -s -X POST http://192.168.0.245:8791/v1/enqueue \
  -H 'Content-Type: application/json' \
  -d '{"action":"perform","player":"Nix","message":"forage"}'

curl -s -X POST http://192.168.0.245:8791/v1/enqueue \
  -H 'Content-Type: application/json' \
  -d '{"action":"interact","player":"Nix","message":"assist:Teome"}'
```

## Suite Phase G

Voir [Phase G — Population de joueurs IA](core3_ia_phase_g_ai_players_population.md).

Le snapshot multi-joueurs `ia_bridge/player_snapshots.json` est la cible v1 pour Lia/Nix et les futurs joueurs IA.
