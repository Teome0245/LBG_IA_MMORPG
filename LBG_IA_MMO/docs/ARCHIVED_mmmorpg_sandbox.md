# Bac à sable MMO Python — archivé (gelé)

**Statut** : **gelé** (bac à sable Python) — **amendement juil. 2026** : le client **Godot** (`lbg_client_godot/`) est **réactivé** comme cible client ; seuls `mmo_server`, `mmmorpg_server`, `web_client` restent gelés côté gameplay Python.  
**Décision** : pivot produit vers **Core3 Prime** (serveur jeu) + **client SWGEmu personnalisé** (launchpad, patches `.tre`).  
**Références** : ADR [`0005-new-mmo-core3-coexistence.md`](adr/0005-new-mmo-core3-coexistence.md) (amendement juin 2026), ADR [`0002-mmo-autorite-pont.md`](adr/0002-mmo-autorite-pont.md) (supersédé pour l’autorité jeu), carnet racine [`../../plan MMMORPG.md`](../../plan%20MMMORPG.md) § *Décision stratégique*.

---

## Périmètre archivé

| Composant | Chemin | Rôle historique |
|-----------|--------|-----------------|
| **`mmo_server`** | `LBG_IA_MMO/mmo_server/` | HTTP slice IA — `WorldState`, `GET /v1/world/lyra`, persistance JSON |
| **`mmmorpg_server`** | `LBG_IA_MMO/mmmorpg_server/` | WebSocket jeu bac à sable — village Lyra / Pixie Seat, protocole `mmmorpg-ws/1` |
| **`web_client`** | `LBG_IA_MMO/web_client/` | Client navigateur MMO (rendu 2D village, dialogue IA) |
| **`lbg_client_godot`** | `LBG_IA_MMO/lbg_client_godot/` | Client Godot phase 0 (login, WASD, WS) — **gelé** |
| Docs associées | `docs/mmmorpg_PROTOCOL.md`, `docs/plan_client_lbg_godot.md`, `docs/ws_contract_mmmorpg_ws_v1.md` | Contrats et études — **lecture seule** |

**Hors périmètre archivé** (reste actif) :

- **Orchestrateur**, agents, backend, Pilot — rang 1 infra / assistant
- **Core3 Prime** (VM 246) — serveur jeu prod
- **Pont IA Core3** — `ia_bridge_screenplay.lua`, sidecar `:8791`, catalogues JSON `content/core3/`
- **Client SWGEmu** — launchpad, patches Prime (`docs/client_dual_launchpad.md`)

---

## Pourquoi le gel ?

1. **Deux moteurs** (Python WS + Core3) créaient une dette ops et une confusion « autorité monde ».
2. Le **bac à sable v1** a rempli son rôle : contrats pont IA ↔ monde, smokes LAN, persona Lyra, protocole WS documenté.
3. **Core3 Prime** est jouable en LAN avec bots IA, économie MVP et personnalisation client SWG — axe produit unique.

---

## Règles à partir de juin 2026

| Action | Autorisé ? |
|--------|------------|
| Nouvelle feature gameplay dans `mmo_server` / `mmmorpg_server` | **Non** |
| Correctif bloquant un smoke ou un test CI existant | **Oui** (minimal) |
| Réutiliser des patterns (pont lecture/écriture, `trace_id`, commits dialogue) côté Core3 | **Oui** — c’est la cible |
| Déployer le rôle `mmo` sur VM 245 pour démo Lyra | **Optionnel** — pas requis pour Prime |
| Supprimer le code archivé du repo | **Non** pour l’instant — conservation en lecture ; archivage physique possible plus tard |

---

## Autorité monde (nouvelle vérité)

| Couche | Autorité actuelle |
|--------|-------------------|
| Jeu temps réel multijoueur | **Core3 Prime** (VM 246, galaxie 3, UDP 44553) |
| Comptes / persistance SWG | **MariaDB** sur VM 245 |
| IA ↔ monde (bots, PNJ pilotes, quêtes data-driven) | **Pont Lua/JSON** + sidecar orchestrateur |
| Slice Lyra / dialogue (legacy) | `mmo_server` + `mmmorpg_server` — **uniquement si stack 245 encore démarrée** |

Voir amendement ADR 0002 et 0005.

---

## Ce qui reste réutilisable

- **Smokes LAN** : `infra/scripts/smoke_lan_*.sh`, `smoke_mmmorpg_*.sh` — référence pour tests pont Core3
- **Contrats** : idempotence `trace_id`, whitelist flags commit, auth interne HTTP — portés vers Prime / sidecar
- **Seed monde** : `mmo_server/world/seed_data/world_initial.json` — inspiration lore / POI, pas chargement direct Core3
- **Agents dialogue** : `agents/dialogue_*` — consommables via pont Core3 (pas via WS Python)

---

## Déploiement legacy (si besoin de redémarrer le bac à sable)

VM **245** (rôle `mmo`) :

```bash
# Depuis poste dev — voir bootstrap.md
./infra/scripts/deploy_vm.sh mmo
# Services typiques : lbg-mmo, lbg-mmmorpg-ws
```

Variables : `LBG_MMO_*`, `MMMORPG_*`, `LBG_MMMORPG_INTERNAL_HTTP_URL` — `infra/secrets/lbg.env.example`.

**Non requis** pour jouer sur Prime (246 + client SWG launchpad).

---

## Client joueur actif (remplacement)

| Ancien | Actuel |
|--------|--------|
| `web_client` / Godot | **Client SWGEmu LBG** (PreCU / Prime) |
| WS `mmmorpg-ws/1` | Protocole SWG natif + patches `.tre` |
| Doc | [`client_dual_launchpad.md`](client_dual_launchpad.md) |

---

## Historique

| Date | Événement |
|------|-----------|
| 2026-04 → 2026-05 | v1 LAN stable — village, Lyra, dialogue, inventaire session |
| 2026-05-12 | ADR 0005 — coexistence Core3 / Python |
| 2026-05-27 | Core3 Prime systèmes monde — bascule prod |
| 2026-06-01 | Godot phase 0 livré puis **gelé** |
| 2026-06-28 | **Gel formel** bac à sable Python + Godot ; focus Core3 + SWGEmu |

---

## Liens

- Plan structuré MMO : [`plan_mmorpg.md`](plan_mmorpg.md) § MMO v1 (périmètre historique Python)
- Runbook Prime : [`core3_prime_runbook.md`](core3_prime_runbook.md)
- Migration (phases historiques) : [`migration_new_mmo_core3.md`](migration_new_mmo_core3.md) — **Phase « bascule prod » atteinte** ; phases Python→Core3 pont restent référence
