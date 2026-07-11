# Runbook — promotion prototype → Core3

**Date** : 2026-07-11  
**Policy** : ADR [`0003-opengame-forge-prototypes.md`](adr/0003-opengame-forge-prototypes.md) — **revue humaine obligatoire**, pas de merge auto dans le tronc MMO.

---

## Quand utiliser ce runbook

- Une tâche `dev_game` (Dédale) a produit une `action_proposal` `prototype_game`
- Un dry-run OpenGame a généré du code dans le sandbox (`LBG_OPENGAME_SANDBOX_DIR`)
- Vous voulez intégrer une brique validée dans **Core3 Prime** (`content/core3/`, sidecar, client Godot)

---

## Rôles

| Rôle | Responsabilité |
|------|----------------|
| **Dédale** (`dev_game`) | Analyse bug / proposition forge |
| **Thémis** (`pm`) | Priorisation, mise à jour plan de route |
| **Humain studio** | Décision go/no-go, revue code, merge |
| **Argus** (`qa`) | Smokes post-promotion |
| **Chœur** (`player_ia`) | Validation sidecar 246 si le prototype touche les bots |

---

## Checklist — avant promotion

- [ ] **Périmètre** : le prototype est bien dans le sandbox OpenGame, pas déjà dans `content/core3/` ou `lbg_client_godot/`
- [ ] **Dry-run OK** : `action_proposal` visible dans `#/team` détail ou `#/assistant`
- [ ] **Exclusion sandbox gelé** : pas de dépendance à `mmmorpg_server` / VM 245
- [ ] **Cible Core3** : le correctif concerne Prime 246 (Lua, sidecar, Godot Prime, pas PreCU)
- [ ] **Secrets** : aucun token / mot de passe dans le diff à promouvoir

---

## Checklist — revue humaine (gate 1)

- [ ] Lire le résumé `action_proposal.summary` et le `context_patch`
- [ ] Ouvrir les fichiers générés dans le sandbox (chemins dans la proposition)
- [ ] Vérifier : pas d’appel réseau arbitraire, pas de `eval`/`exec`, pas d’écriture hors périmètre
- [ ] Décision documentée : **GO** / **NO-GO** / **REWORK** (commentaire PR ou note PM)

---

## Checklist — portage technique (gate 2)

Selon la nature du prototype :

| Type | Destination | Vérifications |
|------|-------------|---------------|
| Gameplay Lua Core3 | `content/core3/lua/` | Compat screenplay, pas de conflit `ia_bridge` |
| Pont IA / snapshots | `tools/core3_ia_sidecar/`, `ia_bridge/` | Endpoints existants inchangés ou versionnés |
| Client Godot Prime | `new_mmo/prime-client/` ou `lbg_client_godot/` | Schémas WS / snapshots |
| Infra / deploy | `infra/scripts/`, systemd | Rollback possible |
| Doc seule | `docs/` | Liens plan de route |

Actions :
- [ ] Copier/adapter le code (pas de symlink sandbox → prod)
- [ ] Adapter imports, chemins VM (`/opt/LBG_IA_MMO`), variables `LBG_*`
- [ ] Mettre à jour `orchestrator/team/subprojects.py` si nouveau sous-projet
- [ ] Tests unitaires ciblés (`pytest` chemins touchés)

---

## Checklist — validation LAN (gate 3)

```bash
# Sidecar + bots
curl -s http://192.168.0.246:8791/healthz
bash infra/scripts/smoke_core3_prime_world_lan.sh

# Équipe virtuelle
bash infra/scripts/test_team_dev_game_workflow_lan.sh

# Godot miroir (si client touché)
bash infra/scripts/smoke_godot_sidecar_mirror_lan.sh
```

- [ ] `player_ia` probe : 3 bots online (Lia/Nix requis)
- [ ] QA smoke LAN vert (140)
- [ ] Pas de régression watchdog Prime (`lbg-core3-prime-watchdog`)

---

## Checklist — déploiement (gate 4)

| VM | Rôle | Commande type |
|----|------|----------------|
| **246** | Core3 + sidecar | `LBG_DEPLOY_ROLE=mmo LBG_VM_HOST=192.168.0.246 bash infra/scripts/deploy_vm.sh` |
| **140** | Orchestrateur | `LBG_DEPLOY_ROLE=core …` |
| **110** | Pilot | `LBG_DEPLOY_ROLE=front …` |

- [ ] `push_secrets_vm.sh` si nouvelles vars
- [ ] `deploy_core3_ia_bridge_vm.sh` si Lua/sidecar modifié
- [ ] Redémarrer services concernés (`systemctl restart lbg-core3-ia-sidecar` sur 246)
- [ ] Vérifier `#/team` et `#/assistant` post-deploy

---

## Checklist — clôture (gate 5)

- [ ] Entrée **plan de route** (`docs/plan_de_route.md` tableau État courant)
- [ ] Brief **Thémis** si réunification multi-fils (`#/team` → Brief réunification)
- [ ] Archiver ou supprimer l’artefact sandbox source (éviter double vérité)
- [ ] Marquer la tâche `dev_game` / job associé comme **done** avec lien commit

---

## Déclenchement via équipe virtuelle

1. `#/team` → rôle **Dédale** → objectif bug/forge → **Lancer**
2. Détail tâche → `action_proposal` → **Forge → Assistant** (dry-run)
3. Après revue humaine : promotion manuelle selon ce runbook
4. Option : `LBG_TEAM_DEV_GAME_AUTO_RUN_FORGE=1` **uniquement** en environnement de test

---

## Références

- [`opengame.md`](opengame.md)
- [`dev_game_workflow`](../orchestrator/team/dev_game_workflow.py)
- [`jalon_client_godot_sidecar_246.md`](jalon_client_godot_sidecar_246.md)
- [`core3_prime_runbook.md`](core3_prime_runbook.md)
