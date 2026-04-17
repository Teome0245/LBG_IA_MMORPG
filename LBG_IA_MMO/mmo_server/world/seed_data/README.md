# Données initiales (seed) du `mmo_server`

Fichier **`world_initial.json`** : scène / PNJ de **départ** lorsqu’aucun état persisté n’existe encore (même schéma que la sauvegarde `world_state.json` — `schema_version`, `now_s`, liste `npcs` avec jauges).

- **Versionné** dans le dépôt pour enrichir le monde sans tout coder en dur.
- Surcharge possible : variable d’environnement **`LBG_MMO_SEED_PATH`** (fichier JSON absolu ou relatif au répertoire de travail du processus).

Après la première sauvegarde, c’est **`LBG_MMO_STATE_PATH`** qui fait foi (reprise au boot).

Voir ADR **`docs/adr/0002-mmo-autorite-pont.md`** pour l’alignement futur avec le serveur jeu (`mmmorpg`).

## PNJ v1 (IDs stables)

Les `npc_id` sont **stables** et **versionnés** (cf. `docs/fusion_spec_monde.md`).

- `npc:smith` — Forgeron
- `npc:merchant` — Marchande
- `npc:innkeeper` — Aubergiste
- `npc:guard` — Garde
- `npc:scribe` — Scribe
- `npc:healer` — Guérisseuse
- `npc:alchemist` — Alchimiste
- `npc:mayor` — Maire
