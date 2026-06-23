# Lia — macro danseur et progression entertainer

Ce document relie la **barre d'action Gally** (F1–F12) aux commandes `pending.jsonl` que Lia exécute via le pont IA.

## Correspondance barre d'action → `perform`

| Touche | Commande Lia | Effet IG |
|--------|----------------|----------|
| F1 | `perform\|Lia\|…\|dance` | Rotation auto (`startdance`) |
| F2 | `…\|dance:basic` | Danse basique |
| F3 | `…\|dance:basic2` | Danse basique 2 |
| F4 | `…\|dance:formal` | Danse formelle |
| F5 | `…\|dance:lyrical` | Danse lente |
| F6 | `…\|dance:popular` | Danse populaire |
| F7 | `…\|dance:exotic` | Danse exotique |
| F8 | `…\|dance:theatrical` | Danse théâtrale |
| F9 | `…\|greet` | Salut |
| F10 | `…\|cheer` | Applaudir |
| F11 | `…\|conduct` | Diriger la scène |
| F12 | `…\|meditate` | Pause |

Source canonique : `content/core3/lia_entertainer_playbook.json` (`macro_slots`).

Exemple manuel (sur la VM Prime, fichier `ia_bridge/pending.jsonl`) :

```text
perform|Lia|tatooine|0|0|0|dance:formal
```

## Progression métier

1. **Cantina** — spectacle et commerce (`/tip Lia <montant>`).
2. **Centre d'entraînement** — `housing_enter|Lia|…|training` puis `learn_entertainer|Lia|…|trainer`.
3. **Instructeur** — NPC `npc:core3_bige_coto` (cell `1189634`) ; paliers dans `lia_entertainer_playbook.json` → `skill_tiers`.
4. **Buffs** (palier 4–5) — `entertainer_buff|Lia|…|audience` pendant qu'elle danse ; `healmind` / `healdamage` si le tier Lua est suffisant.

Commande orchestrateur : scène `entertainer_progress` dans `core3_behavior_profiles.json`.

## Interactions joueur

| Intent | `interact` message | Comportement |
|--------|-------------------|--------------|
| Salut | `greet:Gally` | Approche + salut |
| Groupe (inviter) | `invite_group:Gally` | `enqueueCommand invite` |
| Groupe (accepter) | `accept_group:Gally` | `iaJoinGroup` ou `/join` si invitation en attente |
| Échange | `offer_trade:Gally` / `accept_trade:Gally` | `iaBeginTrade` — fenêtre `/trade` réelle |
| Instructeur | `examine:entertainer` | Visite trainer + nouveau palier |

## Macro client Gally

Pour reproduire la barre sur un perso joueur, créer des macros SWG du type :

```text
/startdance formal
```

Lia n'utilise pas les macros client : l'orchestrateur envoie les mêmes effets via `perform` ou `learn_entertainer`.

## Rotation des danses par palier

| Palier | Danses débloquées |
|--------|-------------------|
| 0 | basic, basic2 |
| 1 | + formal, formal2 |
| 2 | + lyrical, lyrical2, popular |
| 3 | + exotic, exotic2, rhythmic, theatrical |

Sans style explicite (`perform dance`), Lia tourne uniquement dans les danses de son palier (`pickDanceName`).

## Acceptation automatique (tick)

Toutes les ~2 s, pour chaque joueur IA :

- invitation de groupe en attente → `iaJoinGroup`
- joueur relay qui cible Lia en `/trade` → `iaBeginTrade`
- relay qui met des **crédits** dans la fenêtre trade (sans objets) → `iaVerifyTrade` côté Lia ; si les deux ont validé, l'échange se finalise et Lia remercie (+ buff heal si palier ≥ 4)

| Fonction Lua (C++) | Rôle |
|------------------|------|
| `iaBeginTrade(bot, cible)` | Ouvre la fenêtre `/trade` |
| `iaGetTradeTargetOID(joueur)` | OID cible trade en attente |
| `iaHasActiveTrade(bot)` | Session trade active |
| `iaGetTradePartnerMoney(bot)` | Crédits mis par le partenaire |
| `iaTradePartnerVerified(bot)` | Partenaire a cliqué Accepter |
| `iaVerifyTrade(bot)` | → `ok`, `completed` (appelle `handleVerifyTradeMessage`) |

**Prérequis binaire** : fonctions C++ ci-dessus + `iaJoinGroup`, `iaInviteToGroup` dans `DirectorManager` — rebuild Antigravity :

```bash
bash infra/scripts/build_core3_antigravity_vm.sh --sync
bash infra/scripts/install_core3_clean_after_vm_build.sh
bash infra/scripts/deploy_core3_ia_bridge_vm.sh --restart
```

## Fichiers liés

- `content/core3/lua/ia_bridge_screenplay.lua` — danse, trainer, audience, interact
- `agents/src/lbg_agents/lia_entertainer.py` — suggestion d'action autonome
- `content/core3/lia_orchestrator_persona.json` — consignes LLM
