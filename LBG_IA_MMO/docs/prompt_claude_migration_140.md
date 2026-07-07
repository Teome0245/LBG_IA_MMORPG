# Prompt — Claude Code (Windows) : préparer la migration vers VM 140

Copier-coller le bloc ci-dessous dans **Claude Code** sur Windows (ou dans une session `claude chat` / `claude work` pointant vers le dépôt local).

---

## Prompt (copier à partir d'ici)

```
Tu es l'opérateur technique LBG sur le poste Windows. Ta mission : préparer et exécuter la migration du travail de développement non-MMO vers la VM 140 (lbg-backend), en cohabitation avec la prod systemd déjà en place.

## Étape 0 — Lire le handoff (obligatoire)

Ouvre et lis intégralement ce fichier dans le dépôt :
  LBG_IA_MMO/docs/handoff_windows_vers_vm140.md

Ne commence aucune action destructive avant d'avoir complété la section 8 (inventaire local).

## Étape 1 — Inventaire local

1. Localise le clone Git LBG_IA_MMORPG (Windows ou WSL).
2. Vérifie la branche : feature/antigravity-tasks (git fetch && git status).
3. Liste les modifications non commitées ; si présentes, propose commit/push AVANT deploy.
4. Vérifie l'accès SSH : ssh lbg@192.168.0.140 (clé .ppk si PuTTY).
5. Teste les healthz : curl http://192.168.0.140:8000/healthz et :8010/healthz.
6. Complète la section 8 du handoff avec les résultats réels.

## Étape 2 — Plan de migration

Produis un plan numéroté court (max 15 étapes) couvrant :
- Resize Proxmox si RAM < 16 GiB ou disque < 100 GiB (indiquer si action manuelle hyperviseur requise).
- growpart + resize2fs sur 140 si disque agrandi.
- Synchronisation code (/opt/LBG_IA_MMO) via deploy_vm.sh ou git pull.
- push_secrets_vm.sh si lbg.env local diffère.
- bootstrap_claude_on_core140.sh + claude login (interactif — me prévenir).
- Session tmux : lbg-tmux puis claude-lbg.
- Publication UI sur 110 : dev_pilot_workflow.sh --full.
- Vérifications finales (healthz, UI /pilot/v2/, test chat stream).

Pour chaque étape : indique PRÉREQUIS, COMMANDE EXACTE, CRITÈRE DE SUCCÈS, ROLLBACK si échec.

## Étape 3 — Exécution

- Exécute le plan étape par étape.
- Demande mon accord avant : restart systemd, push secrets, resize disque, claude login.
- Ne touche PAS aux VM 245/246 (MMO) sauf demande explicite.
- Ne lance PAS npm run dev sur 140 (réservé au WSL test :5175).
- Ne commite jamais infra/secrets/lbg.env ni node_modules.

## Contraintes

- Compte SSH : lbg (pas sdesharches sur 110/140).
- Prod UI : 110:8080 — API : 140:8000.
- Agent desktop Windows (C:\Agent_IA) RESTE sur Windows.
- Scope : non-MMO uniquement (pilot_shell, backend, agents, infra LAN).

## Livrable attendu

1. Section 8 du handoff remplie.
2. Tableau d'avancement (étape | statut | preuve).
3. Liste des blocages nécessitant action manuelle (Proxmox, claude login, PuTTY).
4. Commande unique de smoke test final.

Commence par confirmer que tu as lu handoff_windows_vers_vm140.md, puis lance l'inventaire.
```

---

## Variante courte (si session déjà dans le repo)

```
Lis LBG_IA_MMO/docs/handoff_windows_vers_vm140.md, complète §8 avec l'état réel de ce poste, puis propose et exécute le plan de migration vers 140 (bootstrap Claude, deploy, tmux). Scope non-MMO. Demande accord avant restart systemd ou claude login.
```

---

## Où placer ce prompt

| Outil | Action |
|-------|--------|
| **Claude Code Windows** | `cd` vers le clone local → `claude work .` → coller le prompt |
| **PuTTY sur 140** | Après bootstrap : `lbg-tmux` → `claude-lbg` → coller la variante courte |
| **WSL** | Possible aussi ; ce prompt cible surtout le poste Windows |

---

*Voir aussi : `docs/fusion_env_lan.md` § VM 140, `infra/scripts/bootstrap_claude_on_core140.sh`.*
