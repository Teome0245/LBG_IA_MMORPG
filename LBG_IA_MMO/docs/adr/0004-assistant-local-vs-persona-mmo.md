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

2. **L’orchestrateur route par intention** : aujourd’hui, le **Mode A** passe par la capability existante **`desktop_control`** → handler **`agent.desktop`** dès que `context.desktop_action` est un objet structuré (voir `orchestrator/router/routes/route_intent.py`). Le worker distant est joignable via **`LBG_AGENT_DESKTOP_URL`** ; sans URL, comportement réservé aux tests / exécution locale (`agents/README.md`). Le **Mode B** (MMO) utilise dialogue, quêtes, pont WS — **ne pas** injecter de `desktop_action` depuis `world_commit` ou le chat joueur sans audit explicite.

3. **Implémentation worker déjà en place** : le module **`windows_agent/Agent_IA`** (sync `infra/scripts/sync_windows_agent.sh`) et **`linux_agent/Agent_IA`** exposent `/healthz` et `/invoke` avec **allowlist**, **dry-run**, **`desktop_approval`**, **audit JSONL** — documenté dans **`docs/desktop_hybride.md`** et **`agents/README.md`** (§ Desktop). C’est l’équivalent concret des garde-fous annoncés (pas besoin d’un second mécanisme `LBG_LOCAL_AGENT_ENABLED` côté core tant que le worker reste **désactivé / non joignable** si non configuré).

4. **Évolution** : nouvelles actions machine (mail, UI, ComfyUI, etc.) s’ajoutent sur le **worker** + contrat `desktop_action.kind`, pas par un canal parallèle — puis mise à jour des ADR / matrice risques si surface sensible.

5. **Lien doux MMO → assistant (phase 1)** : export **volontaire** et **résumé** (ex. `session_summary` : quêtes, ton, choix non secrets) consommable par le mode A — **pas** l’inverse automatique (le MMO ne reçoit pas le contenu des mails).

6. **Modification du MMO par l’IA** : suit les règles existantes — **OpenGame** = forge sandbox (`ADR 0003`) ; modifications du monorepo « canon » = PR / revue humaine ; le serveur autoritatif reste `mmmorpg_server` pour l’état monde (`ADR 0002`).

7. **Curiosité** : encourager l’exploration **documentée** (hypothèses, sources, limites) plutôt que l’accès large non tracé. Toute nouvelle sonde (web, mail, fichiers) = **entrée dans la matrice des risques** + mise à jour de ce ADR ou ADR fils.

## Conséquences

### Positives

- Vision produit (Boîte à idées) **alignée** avec une architecture défendable sur LAN privé.
- Réutilisation du **même orchestrateur / agents** sans fusionner les surfaces d’attaque ; **pas de re-développement** du worker : l’ADR 0004 **nomme** le chemin produit (`local_assistant` ↔ `desktop_control` + worker).

### Négatives / coûts

- Deux piles à maintenir (connecteurs locaux vs contrats MMO).
- Friction utilisateur : bascules ou confirmations pour ne pas mélanger les modes.
- Les outils « general computer use » du marché évoluent vite ; il faudra **revalider** périodiquement les mitigations.

### Mesures de suivi

- Garde-fous worker : **`desktop.env`**, **`LBG_AGENT_DESKTOP_URL`**, approval — suivre **`docs/desktop_hybride.md`** ; exemples de variables dans **`infra/secrets/lbg.env.example`**.
- Mettre à jour `docs/lyra.md` ou `fusion_spec_lyra.md` lorsque le **persona MMO** partage explicitement de la mémoire avec le mode A.
- Entrée « Historique » dans `plan_de_route.md` à chaque jalon livré (capability, pilote UI, smoke).

## Références

- `docs/desktop_hybride.md` — worker Windows/Linux, `desktop_action`, audit, pilot `#/desktop`.
- `agents/README.md` — § Desktop, `LBG_AGENT_DESKTOP_URL`, approval.
- `docs/lyra.md` — IA incarnée, `context.lyra`.
- `docs/adr/0002-mmo-autorite-pont.md` — autorité monde, pont jeu ↔ IA.
- `docs/adr/0003-opengame-forge-prototypes.md` — forge prototypes, pas d’auto-modif du cœur.
- `docs/plan_de_route.md` — priorités 1 (plateforme), 2 (Lyra), 3 (MMO).
- Boîte à idées (inspiration non versionnée) — recentrage « IA curieuse », PC + MMO.
