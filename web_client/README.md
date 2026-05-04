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

La grille de collision côté client (marcher autour des bâtiments) est pilotée par les assets / logique JS du build (ex. `villageCollisionGrid` / chargement grille alignée sur la carte). Après changement de carte ou de marge bâtiments, regénérer ou resynchroniser la grille avec le serveur selon le flux du dépôt.

## Ramassage (stub)

Touche **E** ou bouton **RAMASSER** (HUD PNJ) : envoi d’un `move` avec `world_commit` (`player_item_*`) vers le PNJ sélectionné si le joueur est assez proche. Sans LLM — voir `LBG_IA_MMO/docs/mmmorpg_PROTOCOL.md`.

## Déploiement LAN

Recette pas à pas (build, `deploy_web_client.sh`, VM front, redémarrage `mmmorpg`) : **`LBG_IA_MMO/docs/fusion_env_lan.md`** (section *Recette express — client MMO*). Variables d’environnement : même fichier et `infra/secrets/lbg.env.example`.
