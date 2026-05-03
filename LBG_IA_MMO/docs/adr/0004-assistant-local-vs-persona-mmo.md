# ADR 0004 — Assistant poste de travail et persona MMO (même « esprit », périmètres séparés)

## Statut

**Accepté** — 2026-05-05

## Contexte

La vision produit inclut à la fois :

1. **Un assistant sur la machine / l’infra** : actions concrètes (applications locales, recherche web, messagerie, etc.), avec interaction naturelle (« ouvre Notepad et écris… », « cherche le site de… », « y a-t-il un mail de… »).
2. **Une incarnation dans le MMO** : dialogue avec les PNJ, quêtes, apprentissage dans un monde **simulé** et **borné**, aligné avec `mmmorpg_server`, `web_client` et le pont jeu ↔ IA.
3. **À terme** : capacités d’**améliorer** le MMO (contenu, systèmes), sous **contrôle humain** et garde-fous — proche de l’esprit « IA curieuse » décrit dans la Boîte à idées (non contractuelle).

Sans cadrage, les risques sont majeurs : **fuite de contexte** entre monde privé (mails, fichiers) et monde partagé (MMO), **exécution non autorisée** sur l’OS, **confusion identitaire** (un même prompt qui mélange les deux mondes), et **dérive** vers un agent trop puissant sans audit.

## Décision

1. **Deux modes explicites** (produit et technique) :
   - **Mode A — `local_assistant`** : intention ciblée poste de travail / infra **du propriétaire**. Secrets, chemins et outils (navigateur, shell, IMAP, etc.) sont **isolés** de la session MMO et des joueurs.
   - **Mode B — `mmo_persona`** : intention ciblée **monde simulé** (`context` WS, PNJ, quêtes). Aucune lecture directe du coffre mail ou du disque personnel **via** ce mode sans passer par une capability **séparée** et un **opt-in** explicite côté client « hors session partagée ».

2. **L’orchestrateur route par intention** : le classifieur (ou métadonnées d’appel) doit distinguer `local_assistant` vs `mmo_persona` (et le reste). **Interdiction** de router une action OS sensible depuis un message joueur MMO **sans** pont dédié revu (pas d’« injection » depuis `world_commit` vers le bureau).

3. **Première capability « desktop » (future)** : tout accès machine réel passe par une **capability déclarée** (même squelette), **désactivée par défaut**, avec **audit JSONL** (qui, quoi, quand, paramètres redactés), **timeout**, **allowlist** d’actions, et **double confirmation** ou variable d’environnement du type `LBG_LOCAL_AGENT_ENABLED=1` sur la machine concernée uniquement.

4. **Lien doux MMO → assistant (phase 1)** : export **volontaire** et **résumé** (ex. `session_summary` : quêtes, ton, choix non secrets) consommable par le mode A — **pas** l’inverse automatique (le MMO ne reçoit pas le contenu des mails).

5. **Modification du MMO par l’IA** : suit les règles existantes — **OpenGame** = forge sandbox (`ADR 0003`) ; modifications du monorepo « canon » = PR / revue humaine ; le serveur autoritatif reste `mmmorpg_server` pour l’état monde (`ADR 0002`).

6. **Curiosité** : encourager l’exploration **documentée** (hypothèses, sources, limites) plutôt que l’accès large non tracé. Toute nouvelle sonde (web, mail, fichiers) = **entrée dans la matrice des risques** + mise à jour de ce ADR ou ADR fils.

## Conséquences

### Positives

- Vision produit (Boîte à idées) **alignée** avec une architecture défendable sur LAN privé.
- Réutilisation du **même orchestrateur / agents** sans fusionner les surfaces d’attaque.
- Piste claire pour un **MVP** : un seul outil local trivial (ex. ouvrir un éditeur + coller du texte) derrière une capability bornée.

### Négatives / coûts

- Deux piles à maintenir (connecteurs locaux vs contrats MMO).
- Friction utilisateur : bascules ou confirmations pour ne pas mélanger les modes.
- Les outils « general computer use » du marché évoluent vite ; il faudra **revalider** périodiquement les mitigations.

### Mesures de suivi

- Avant première capability locale : schéma d’audit + variable de feature flag documentée dans `lbg.env.example`.
- Mettre à jour `docs/lyra.md` ou `fusion_spec_lyra.md` lorsque le **persona MMO** partage explicitement de la mémoire avec le mode A.
- Entrée « Historique » dans `plan_de_route.md` à chaque jalon livré (capability, pilote UI, smoke).

## Références

- `docs/lyra.md` — IA incarnée, `context.lyra`.
- `docs/adr/0002-mmo-autorite-pont.md` — autorité monde, pont jeu ↔ IA.
- `docs/adr/0003-opengame-forge-prototypes.md` — forge prototypes, pas d’auto-modif du cœur.
- `docs/plan_de_route.md` — priorités 1 (plateforme), 2 (Lyra), 3 (MMO).
- Boîte à idées (inspiration non versionnée) — recentrage « IA curieuse », PC + MMO.
