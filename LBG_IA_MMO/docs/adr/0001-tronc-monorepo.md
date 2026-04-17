# ADR 0001 — Tronc unique : monorepo LBG_IA_MMO

## Statut

**Accepté** — 2026-04-12

## Contexte

Le projet assemble trois lignées historiques :

- **`LBG_IA_MMO/`** (ce dépôt) : orchestrateur léger, agents, `mmo_server`, déploiement VM / systemd.
- **`~/projects/LBG_IA/`** : UI Vue, Postgres, `RouterIA`, écosystème Docker.
- **`~/projects/mmmorpg/`** : serveur jeu WebSocket, protocole, monde multijoueur.

Sans règle explicite, la fusion risque soit un **big bang** peu maîtrisable, soit une **double maintenance** indéfinie sur plusieurs dépôts. La vision produit cible est un **dépôt unique**, une **exploitation sur trois machines** (LAN), et un **comportement cohérent** documenté (`plan_fusion_lbg_ia.md`, `fusion_env_lan.md`).

## Décision

1. **Tronc Git unique** : le référentiel canonique du projet fusionné est le monorepo **`LBG_IA_MMO/`** (sous `LBG_IA_MMORPG/`). C’est là que vivent les évolutions de code, la documentation opérationnelle et, à terme, le déploiement unifié.

2. **Dépôts `LBG_IA` et `mmmorpg` en lecture seule pour la fusion** : on **ne modifie pas** ces arbres pour intégrer le produit. Ils servent de **référence** (comparaison, reprise de versions, lecture des specs). Toute fonctionnalité à rapprocher se **reproduit**, **adapte** et **commit** dans **`LBG_IA_MMO/`**.

3. **Exploitation** : la cible reste **trois hôtes** sur le LAN (répartition par rôle dans `docs/fusion_env_lan.md`), indépendamment du nombre de dépôts sources pendant la migration.

4. **Suites techniques** : les choix d’architecture plus fins (autorité monde vs slice IA `mmo_server`, pont jeu ↔ IA, structure des dossiers du code porté) feront l’objet d’**ADR ultérieurs** ; le présent ADR ne les préempte pas.

## Conséquences

### Positives

- Une **seule** ligne d’historique Git pour le produit assemblé ; revues et CI centralisés.
- Traçabilité claire : chaque import depuis une source est un **changement revu** dans le monorepo.
- Alignement avec l’objectif « **un projet complet cohérent** » sans dépendre à long terme de patches croisés entre dépôts externes.

### Négatives / coûts

- **Portage** : duplication initiale de code et risque de dérive par rapport aux dépôts sources tant que la migration n’est pas terminée.
- **Discipline** : il faut noter les **références** (commit ou tag source) lors des imports majeurs pour pouvoir comparer ou réimporter.

### Mesures de suivi

- Jalons et phases : `docs/plan_fusion_lbg_ia.md` ; suivi opérationnel : `docs/plan_de_route.md`.
- En cas de conflit entre ce ADR et le code, **le code réellement mergé dans `LBG_IA_MMO/`** et les **ADR suivants** font foi ; mettre à jour ce document si la décision est amendée.

## Références

- `docs/plan_fusion_lbg_ia.md` — plan de fusion (phases A→E).
- `docs/fusion_env_lan.md` — topologie trois machines et variables d’environnement.
- `docs/lexique.md` — définition générale des **ADR** et vocabulaire du projet.
- `docs/adr/0002-mmo-autorite-pont.md` — autorité monde (`mmmorpg` vs `mmo_server`) et pont jeu ↔ IA.
