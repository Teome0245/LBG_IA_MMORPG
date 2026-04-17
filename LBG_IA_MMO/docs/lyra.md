# Lyra (IA incarnée) — spécification de base

Ce document synthétise `Lyra 20260409.txt` et l’intègre au projet.

**Fusion (phase B)** : alignement assistant vs PNJ, enveloppe `kind`, plages — voir **`fusion_spec_lyra.md`** (ne remplace pas ce fichier pour le comportement **actuel** du code).

## Nommage / version

- Version : **Lyra 2.0**
- Noms candidats : **Alètheia**, **Aphélie**, **Arété**, **Coalémos**

## Objectifs fonctionnels

Construire une IA “vivante”, interactive, capable de :
- afficher des **jauges** en temps réel
- réagir visuellement (couleurs, transitions)
- permettre d’augmenter/diminuer chaque jauge
- simuler des situations (fatigue, impatience, stress, etc.)
- influencer le comportement de Lyra dans l’orchestrateur et/ou le MMO

## Plan d’implémentation (cible)

- **Contrôles UI** : modifier les jauges depuis un frontend (à introduire ultérieurement)
- **State** : un `LyraState` accepté/validé côté backend/orchestrator
- **Rafraîchissement** : timestamp, uptime, refresh automatique
- **Widget** : `LyraWidget` (affichage + couleurs dynamiques + update auto)
- **Actions rapides** : “épuiser”, “calmer”, presets de situations
- **Améliorations** : animations, transitions, réactions comportementales selon jauges

## Point d’intégration actuel (squelette)

Dans le squelette actuel, l’équivalent minimal côté simulation est `mmo_server/lyra_engine/gauges.py` (jauges + `step(dt)`).
La partie UI/front n’est pas encore créée : elle sera documentée/implémentée dans une étape dédiée.

## Contrat d’état (brouillon — orchestrateur / agents)

Objectif : permettre à terme de **faire circuler** un état Lyra dans la chaîne `backend → orchestrator → agents` sans imposer encore un moteur unique.

**Convention proposée** (évolutive ; à valider avant implémentation stricte) :

| Direction | Champ | Rôle |
|-----------|--------|------|
| Entrée | `context.lyra` | Objet JSON optionnel : métadonnées (`version`, `dt_s`, …) et éventuellement `gauges` (voir ci‑dessous). |
| Sortie | `output.lyra` | Objet JSON optionnel : état **après** traitement (echo ou simulation). |

**Jauges moteur (`lyra_engine.gauges`)** — si `context.lyra.gauges` contient au moins une des clés **`hunger`**, **`thirst`**, **`fatigue`** (valeurs 0–1, flottants), le stub **`agent.fallback`** applique `GaugesState.step(dt_s)` via **`lbg_agents.lyra_bridge`** lorsque le paquet **`mmo_server`** est installé dans le même venv (`install_local.sh`). `dt_s` (secondes simulées, défaut 60) est repris dans `output.lyra.meta.dt_s`. Les jauges « libres » (ex. stress seul, sans hunger/thirst/fatigue) restent en **echo** sans pas de simulation.

Règles :
- Absence de `context.lyra` : comportement inchangé pour les handlers existants.
- Les handlers qui ne parlent pas Lyra **ignorent** ces champs.
- Validation stricte (schéma Pydantic, limites de jauges) viendra **après** un premier passthrough manuel ou pilot.

**UI `/pilot/`** : si `result.output.lyra` (ou `remote.lyra`) est présent, la réponse formatée affiche un bloc **Lyra (output)** (JSON indenté, lecture seule).

**Echo / simulation (agents)** : le handler `agent.fallback` (stub `minimal_stub` / `_echo`) renvoie `output.lyra` : echo si pas de jauges moteur reconnues, sinon jauges mises à jour si `lyra_engine` est disponible.

**Pilot** : preset **« Lyra (test) »** — texte sans mots-clés métier afin que l’orchestrateur garde l’intent **`unknown`** (et **`npc_name`** absent pour éviter le forçage dialogue).

**Dialogue (`agent.dialogue`)** : si le routage mène au dialogue HTTP et que **`context.lyra`** contient des jauges moteur, **`dispatch`** applique le même pas **`step_context_lyra_once`** avant `POST /invoke`, transmet le **`context` mis à jour** à l’agent, et ajoute **`output.lyra`** à la réponse orchestrateur (visible dans `/pilot/`).

**LLM** : `dialogue_llm.build_system_prompt` ajoute au **system prompt** un résumé lisible des jauges (`faim`/`soif`/`fatigue` en ~%, optionnel `stress`/`patience`) et une consigne pour que le PNJ **reflète** l’état sans citer de pourcentages au joueur.

### Boucle monde (MMO) → `context.lyra`

- Variable **`LBG_MMO_SERVER_URL`** : URL du serveur MMO HTTP (ex. local `http://127.0.0.1:8050`, LAN `http://192.168.0.245:8050` ; unité systemd `lbg-mmo-server`).
- Champ **`context.world_npc_id`** (ex. `npc:smith`) : si l’URL est définie, le **backend** appelle `GET /v1/world/lyra?npc_id=...` et **remplit / remplace** `context.lyra` avec un instantané dont **`meta.source` = `mmo_world`** (jauges déjà avancées par le **tick** côté `mmo_server`).
- **`meta.skip_mmo_sync`** sur `context.lyra` (truthy) : désactive cette fusion pour l’appel courant (tests ou override manuel).
- Côté agents, **`step_context_lyra_once`** **ne ré-applique pas** `lyra_engine.gauges.step` lorsque **`meta.source` = `mmo_world`** (évite un double pas).

### Pont jeu (WS) → `context.lyra` (priorité) + fallback monde

Quand le serveur jeu **`mmmorpg_server`** expose son **HTTP interne** et que le backend est configuré avec **`LBG_MMMORPG_INTERNAL_HTTP_URL`**, le backend tente d’abord :

- `GET /internal/v1/npc/{npc_id}/lyra-snapshot` → instantané avec **`meta.source` = `mmmorpg_ws`** (lecture seule).

Si ce snapshot est indisponible (timeout / 401 / 404 / erreur réseau), le backend **retombe** sur `mmo_server` si **`LBG_MMO_SERVER_URL`** est défini (voir section précédente) : **`meta.source` = `mmo_world`**.

**Réputation (signal narratif v1)** : dans les deux sources, `lyra.meta.reputation.value` est un **entier** borné (typiquement \([-100, 100]\)). Côté dialogue, le LLM reçoit ce signal dans le **system prompt** (sans afficher un “score” au joueur) et la **clé de cache** dialogue inclut la réputation pour éviter des réponses figées quand elle change.

**Cohérence fallback** : lorsqu’un commit `reputation_delta` est appliqué via le backend, un **double-write best-effort** met aussi à jour `mmo_server` (`POST /internal/v1/npc/{npc_id}/reputation`, token optionnel `LBG_MMO_INTERNAL_TOKEN`) afin que le fallback `mmo_world` reste aligné avec l’état “jeu WS”.

Prochaine étape produit : enrichir un agent réel ou l’orchestrateur pour produire / transformer `output.lyra` selon la simulation.

