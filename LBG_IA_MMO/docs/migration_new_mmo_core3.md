# Migration / intégration **new_mmo** (Core3) ↔ monorepo **LBG_IA_MMO**

**Statut** : document d’ingénierie — **aucune obligation** de timeline tant que les phases ci-dessous ne sont pas explicitement validées en prod.

**Décision de gouvernance** : **`docs/adr/0005-new-mmo-core3-coexistence.md`**.

---

## 1. Objectif

Permettre de **traiter `new_mmo` comme une lignée officielle** du projet (build, ops, LAN) **sans** confondre :

- le **serveur jeu Core3** (C++, MySQL `swgemu`, binaire `core3`) ;
- la **stack MMO Python** du monorepo (`mmmorpg_server` + `mmo_server`).

À terme, une **équipe** peut décider de **remplacer** tout ou partie de la stack Python par Core3 ; ce document fixe **les prérequis** et **l’ordre des travaux**, pas une date d’exécution.

---

## 2. Matrice des briques (rappel)

| Brique | Technologie | Rôle vis-à-vis LBG_IA_MMO |
|--------|-------------|---------------------------|
| **`mmmorpg_server/`** | Python, WebSocket | Client web / outils — protocole documenté côté monorepo. |
| **`mmo_server/`** | Python, FastAPI HTTP | Lyra PNJ, `WorldState`, appels **`LBG_MMO_SERVER_URL`** depuis le **backend**. |
| **`new_mmo` / Core3** | C++, MySQL | Serveur jeu SWGEmu ; **protocole et persistance différents**. |

**Conclusion** : il n’existe pas de « remplacement par le même port » : tout bascule passe par **clients + ponts + variables d’environnement + systemd**.

---

## 3. Où placer le code **new_mmo** dans le workflow

### Option A — Clone voisin (recommandé pour l’instant)

- Chemin typique : **`~/projects/new_mmo`** (déjà utilisé en pratique sur les postes / VMs).
- Avantages : pas d’impact sur la taille du dépôt Git **LBG_IA_MMO** ; pas de sous-module à maintenir.

### Option B — Répertoire `third_party/new_mmo` (clone local, non versionné)

- Créer **`LBG_IA_MMO/third_party/new_mmo/`** et y cloner le dépôt `new_mmo`.
- Le répertoire est **ignoré par Git** (voir `third_party/README.md`) pour éviter de committer des millions de fichiers / binaires.

### Option C — `git submodule` (optionnel)

À utiliser si l’équipe dispose d’une **URL Git stable** pour `new_mmo` et accepte :

- la discipline **`git submodule update`** ;
- l’adaptation éventuelle de la **CI** (build C++ séparé).

Commande type (à adapter à l’URL réelle) :

```bash
cd LBG_IA_MMO
git submodule add <URL_GIT_NEW_MMO> third_party/new_mmo
```

Si le submodule est adopté, **retirer** ou **ajuster** l’entrée `third_party/new_mmo/` dans `.gitignore` pour que seul le pointeur submodule soit versionné (pas les artefacts de build).

---

## 4. Phases de migration (vers un remplacement « entier » si souhaité)

### Phase 0 — Documentation et inventaire (**en cours**)

- ADR **0005** accepté.
- Ce fichier + `third_party/README.md`.
- Inventaire : ports Core3 vs `MMMORPG_PORT` / `LBG_MMO_SERVER_URL` / HTTP interne **8773**, etc.

### Phase 1 — Cohabitation contrôlée (LAN / lab)

- VM ou lab où **Core3** et **Python** tournent avec des **ports distincts** documentés.
- Runbook : démarrage / logs (`/tmp/core3.log` ou équivalent), sauvegardes **MariaDB `swgemu`**.

### Phase 2 — Pont ou réécriture client

- Définir **qui** parle à **qui** :
  - soit le **client LBG** (web / autre) est réécrit ou adapté pour le **protocole Core3** ;
  - soit une **façade** traduit un sous-ensemble d’événements (coût élevé, à trancher par ADR).

### Phase 3 — Bascule et dépréciation

- Mettre à jour **`infra/scripts/deploy_vm.sh`** (ou script sœur **`infra/scripts/deploy_core3.sh`**) pour le rôle **mmo** si la prod ne déploie plus Python sur 245.
- Mettre à jour **`infra/secrets/lbg.env.example`** : retrait ou commentaire des variables **`MMMORPG_*` / `LBG_MMO_SERVER_URL`** si elles ne s’appliquent plus.
- **Tests de fumée** : remplacer ou dupliquer les **`smoke_*`** actuels par des checks Core3 + client.
- **Amender ADR 0002** (ou ADR successeur) : nouvelle **autorité monde**.

---

## 5. Variables et contrats à revisiter lors d’une bascule

| Zone | Exemples (non exhaustif) |
|------|---------------------------|
| Backend / pilot | `LBG_MMO_SERVER_URL`, `LBG_MMO_INTERNAL_TOKEN`, proxies pilot |
| Jeu WS | `MMMORPG_*`, `LBG_MMMORPG_INTERNAL_HTTP_*`, pont **`MMMORPG_IA_*`** |
| Clients | `web_client`, URLs WS, tout script LAN |
| Déploiement | `deploy_vm.sh` rôle **mmo**, unités **systemd** `lbg-mmmorpg-ws`, `lbg-mmo-server` |

---

## 6. Checklist avant de **désactiver** `mmmorpg_server` ou `mmo_server` en prod

- [ ] Client(s) validés contre **Core3** seul.
- [ ] Stratégie **Lyra / PNJ / dialogue** : conservée via **façade HTTP**, intégrée dans Core3, ou abandonnée sur ce chemin.
- [ ] Sauvegardes **DB + fichiers monde** + plan de retour arrière.
- [ ] Runbook **systemd** + monitoring + logs rotatifs.
- [ ] Revue **sécurité** (exposition LAN, tokens, MariaDB).

---

## 7. Références croisées

- `docs/plan_fusion_lbg_ia.md` — vision fusion (mettre à jour le tableau des dépôts).
- `docs/fusion_env_lan.md` — IPs et variables LAN.
- `docs/adr/0002-mmo-autorite-pont.md` — autorité Python actuelle.
- `mmmorpg_server/README.md`, `mmo_server` — comportement actuel du monorepo.
