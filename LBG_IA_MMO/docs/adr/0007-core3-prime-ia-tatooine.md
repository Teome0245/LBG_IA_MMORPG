# ADR 0007 — Pont IA Core3 : Serveur Prime + Tatooine

**Statut** : accepté (2026-05-21)  
**Contexte** : pont v0 déployé sur `core3-clean` ; besoin de borner le périmètre avant PNJ / monde vivant.

## Décision

1. **Une seule instance jeu** pour le pont IA LBG : **LBG MMO Serveur Prime** (`core3-clean`, galaxy 3).
2. **Cible IA / monde vivant** : planète **`tatooine`** en priorité. **`Core3.ZonesEnabled`** inclut au minimum **`tutorial`** pour éviter les erreurs login (« planet disabled ») des persos existants.
3. **Joueur cobaye** : compte **`Bot_IA`**, `admin_level = 0`, piloté via file `ia_bridge/pending.jsonl` + sidecar HTTP **8791** (systemd `lbg-core3-ia-sidecar`).
4. **PreCu** (`core3-swgemu`) : pas de pont IA tant qu’ADR non révisé.
5. **Renommage planète** : autorisé côté **nom affiché** client ; l’**id zone** (`tatooine` ou successeur) reste la clé dans config, Lua et `CORE3_IA_ZONE`.

## Conséquences

- Builds / ops IA ciblent **`/opt/lbg-new-mmo-clean`** uniquement.
- Roadmap « monde vivant » (`plan MMMORPG.md`) s’applique d’abord à **Tatooine Prime**, puis extension planète par planète.
- La stack **mmmorpg + mmo_server** reste distincte (ADR 0005) jusqu’à convergence explicite.

## Phases suivantes

| Phase | Contenu |
|-------|---------|
| A | Sidecar systemd, Bot_IA, Tatooine, `say` / `switch_zone`, prénom `Lia` — **terminée** (2026-05-22, smoke `[IA]` OK) |
| B | Snapshot joueur → contexte LLM — **terminée** (`docs/core3_ia_phase_b_snapshot.md`, rebuild `core3-clean`) |
| C | PNJ pilotes (registry `npc_id` ↔ mobile Core3) — **terminée** (`docs/core3_ia_phase_c_npc_pilots.md`) |
| D | Joueur bot réservé **Bot_IA** / **Lia Bot** headless (`core3client`) — **v1** (`docs/core3_ia_phase_d_headless_bot.md`) |
| (futur) | Autres comptes joueur bot si besoin |
| E | Ticks sociaux / monde vivant (3 niveaux de simulation) |

## Références

- `docs/core3_ia_prime_tatooine.md`
- `docs/core3_ia_player_bridge.md`
- `plan MMMORPG.md` (vision monde vivant)
