# Client web MMO (`web_client`)

Build statique du monde *browser* : rendu tuilé, PNJ, dialogue, journal de quêtes.

## Build

```bash
cd web_client
npm install
npm run build
```

Les artefacts servis en prod sont typiquement dans `web_client/dist/` (voir script `package.json`).

## Collisions village

Après connexion au WS, le client tente **`GET /v1/world/collision-grid`** sur le **`mmo_server`** (même hôte que le champ IP de connexion ; ports essayés : **8050**, 8000, 8010, …). Le JSON `watabou_grid_v1` alimente `src/villageCollisionGrid.js` : prédiction locale (ne pas envoyer de `move` vers une tuile non franchissable).

**CORS** : le navigateur doit être autorisé par le `mmo_server` — `LBG_MMO_CORS_ORIGINS` (liste d’origines) ou, en poste de dev si la liste est vide, `LBG_MMO_CORS_DEV=1` (localhost Vite 5173 / preview 4173). Voir `LBG_IA_MMO/mmo_server/README.md` et `infra/secrets/lbg.env.example`.

### Carte “jolie” vs grille collisions (piège classique)

Le PNG Watabou (`pixie_seat.png`) est **artistique** et n’est pas garanti “métrique” (cadrage/flip/échelle). La **vérité** gameplay reste la grille collisions (`pixie_seat.grid.json`).  

Dans ce client, on applique une **correction** au fond Watabou (flip/scale) pour le faire coller à la grille :

- par défaut : **`pflipz=1`** et **`ps≈0.714`** (calibré pour Pixie Seat)
- debug : superposition de la grille “moche” (`overlay=1`) et réglages :
  - `overlay=1&alpha=0.45` : affiche le calque premium par‑dessus
  - `flipz=1` : flip N/S du calque overlay (debug seulement)
  - `dx`/`dz` (mètres) : décalage overlay (debug seulement)
  - `os` : scale overlay (debug seulement)

Exemple : `...?overlay=1&alpha=0.45` (le fond est corrigé automatiquement).

## Ramassage (stub)

Touche **E** ou bouton **RAMASSER** (HUD PNJ) : envoi d’un `move` avec `world_commit` (`player_item_*`) vers le PNJ sélectionné si le joueur est assez proche. Sans LLM — voir `LBG_IA_MMO/docs/mmmorpg_PROTOCOL.md`.

## Reconnexion (session WS)

Le client stocke `welcome.session_token` et le renvoie automatiquement au reconnect dans `hello.resume_token`.
Cela permet de reprendre le même `player_id` (si `MMMORPG_SESSION_TTL_S` n’est pas expiré côté serveur).

## Dialogue — mémoire de conversation (multi-tours)

Le client envoie `ia_context.history` (tours précédents **user** / **assistant**, par PNJ) au serveur ; le pont fusionne avec le résumé session. L’historique est **local à la session** (perdu à la déconnexion). Pour que le PNJ tienne compte des contradictions du joueur, le prompt agent inclut une consigne de cohérence (pas de persistance LLM hors fil de messages).

## Déploiement LAN

Recette pas à pas (build, `deploy_web_client.sh`, VM front, redémarrage `mmmorpg`) : **`LBG_IA_MMO/docs/fusion_env_lan.md`** (section *Recette express — client MMO*). Variables d’environnement : même fichier et `infra/secrets/lbg.env.example`.
