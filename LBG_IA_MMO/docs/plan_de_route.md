# Plan de route (LBG_IA_MMO)

Document de suivi : **priorités**, **livrables cibles** et **règle de mise à jour**. À relire et à ajuster à chaque jalon significatif.

## Ordre de priorité (résumé)

| Priorité | Thème | Rôle |
|----------|--------|------|
| **0** | Documentation | Transverse : rédiger et **mettre à jour à chaque étape** |
| **1** | Cœur plateforme | Orchestrateur, backend, agents fonctionnels, interface utilisateur (pilotage + monitoring) |
| **2** | Lyra | Ensemble fonctionnel et technique autour de l’IA incarnée (voir `lyra.md`) |
| **3** | MMO | Monde, simulation serveur, gameplay systémique (voir `plan_mmorpg.md`) |
| **F** | **Fusion vers un seul repo** | **Objectif** : **un dépôt** (`LBG_IA_MMO/`), **trois machines** (LAN), projet **cohérent**. Les dépôts **`LBG_IA`** et **`mmmorpg`** restent **sources en lecture** ; on **reproduit et intègre** ici — **ne pas disperser** : **`plan_fusion_lbg_ia.md`** (phases A→E). |

La numérotation **0** = toujours actif en parallèle des autres priorités. La priorité **F** est **transverse** : elle peut coexister avec 1–3 tant que la fusion est en cours.

---

## Étoile du nord produit (priorisée)

Prise en compte explicite de la note **`Boite à idées/20260428_1220_on ce recentre.txt`** : *IA incarnée sur le poste / l’infra* (ex. bloc-notes dictée, recherche web, lecture mail), **puis** présence au **cœur du MMO** pour apprendre dans un monde simulé, **puis** capacité à **faire évoluer** le MMO sous contrôle humain. Les idées brutes restent dans `Boite à idées/` ; **ici** on fixe l’ordre de priorité pour le monorepo.

| Rang | Objectif | Piste technique / doc |
|------|----------|------------------------|
| **1** | **Assistant sur PC et infra** — actions concrètes, bornées, observables | `docs/desktop_hybride.md`, capability **`desktop_control`** → `agent.desktop`, workers `windows_agent` / `linux_agent` ; `docs/adr/0004-assistant-local-vs-persona-mmo.md` |
| **2** | **Même famille cognitive côté MMO** — apprentissage / persona dans le bac à sable | `mmmorpg_server`, `agents/dialogue_*`, Lyra (`docs/lyra.md`) ; séparation **assistant local** vs **persona MMO** (ADR 0004) |
| **3** | **Évolution du monde par l’IA** — jamais sans repreneur humain sur le tronc | Forge OpenGame (`docs/adr/0003-opengame-forge-prototypes.md`), Brain / DevOps **opt-in** + jetons, pas d’écriture sauvage sur le moteur autoritaire |

**Règle** : tant que le **rang 1** n’est pas suffisamment fiable (dry-run, allowlists, audit, parcours réels « Notepad / URL / mail » progressivement), les gros chantiers **rang 3** sur le dépôt restent **secondaires** dans la planification exécutoire — sans rejeter la vision long terme.

---

## Fil produit ↔ documentation (continuité)

**Règle** : tout incrément **mergé ou déployé** qui change un contrat, une UI pilot / MMO, ou le comportement attendu par un opérateur doit **conserver le fil** en :

1. ajoutant une ligne datée dans **Historique** (section plus bas) — *obligatoire* pour toute livraison notable ;
2. mettant à jour **au moins une** entrée du tableau ci‑dessous quand la livraison touche le périmètre concerné (même petit paragraphe ou lien).

| Fil | Source inspiration | Données versionnées | Code consommateur | Doc pivot |
|-----|-------------------|---------------------|--------------------|-----------|
| Idées lore / listes longues | `Boite à idées/` (non contractuel) | `LBG_IA_MMO/content/world/*.json` | `lbg_agents.world_content`, registre PNJ, `mmmorpg_server.world_catalog`, entités `race_id` | `plan_mmorpg.md`, `agents/README.md`, `pilot_web/README.md` |
| **Poste + MMO unifiés (vision nord)** | `Boite à idées/` (ex. `20260428_1220_on ce recentre.txt`) | — | `agent.desktop`, orchestrateur, pont dialogue MMO, Lyra | `vision_projet.md`, `desktop_hybride.md`, `docs/adr/0004-assistant-local-vs-persona-mmo.md`, § *Étoile du nord* ci‑dessus |
| Pilot & proxies backend | — | — | `backend/api/v1/routes/pilot.py` | `fusion_etat_des_lieux_v0.md`, `bootstrap.md` |
| Snapshot Lyra / PNJ monde | `docs/lyra.md`, `fusion_spec_lyra.md` | état serveur + catalogue races | `mmmorpg_server` (`build_lyra_snapshot`, …) | `plan_de_route` (Historique), `lyra.md` si contrat change |

**Variable optionnelle** : `LBG_WORLD_CONTENT_DIR` (répertoire contenant `races.json` et `creatures.json`) — à documenter dans `infra/secrets/lbg.env.example` si l’équipe standardise un chemin hors repo sur VM.

---

## Priorité 0 — Documentation

**Objectif** : ne pas perdre le fil technique et produit ; garder une source de vérité alignée avec le code et l’infra.

**À faire /À maintenir** :

- Tenir à jour : `docs/architecture.md`, `bootstrap.md`, ce fichier `plan_de_route.md`, et les docs thématiques (`vision_projet.md`, `lyra.md`, `plan_mmorpg.md`) lorsque le comportement ou les déploiements changent.
- **Continuité** : suivre la section **Fil produit ↔ documentation** ci‑dessus pour ne pas disperser les mises à jour (une évolution = Historique + doc du bon pivot).
- **`docs/lexique.md`** : définitions (**ADR**, composants, acronymes projet) pour la **transmission** / onboarding ; compléter lorsqu’un terme nouveau devient stable (nouvelle capability, nouveau service, jargon fusion).
- **Fusion multi-dépôts → un seul repo** : **`LBG_IA`** et **`mmmorpg`** comme **références non modifiées** ; intégration dans **`LBG_IA_MMO/`** uniquement. Tenir à jour **`docs/plan_fusion_lbg_ia.md`** (phases, ADR, pont jeu ↔ IA, topologie **3 VM**) à chaque jalon ; jalons inventaire / état des lieux : **`fusion_etat_des_lieux_v0.md`** ; specs phase B : **`fusion_spec_*.md`**, **`fusion_pont_jeu_ia.md`** ; ne pas dupliquer la vision fusionnée ailleurs sans lien vers ces fichiers.
- **Promouvoir le dev vers la prod (VM privée)** : `LBG_IA_MMO/infra/scripts/deploy_vm.sh` depuis le poste de travail (ex. WSL) ; tu peux **ne pas** lancer la stack locale et valider **sur la VM** uniquement (`curl`, `/pilot/`, systemd). Les tests `pytest` en local restent recommandés avant un merge sensible. Détail : `bootstrap.md` (*Pousser les évolutions* → *sans exécuter les services en local*).
- **Environnement secrets** : toute réorganisation des sections ou des variables de `infra/secrets/lbg.env` (fichier local non versionné) doit être **reflétée dans `infra/secrets/lbg.env.example`** dans le même changement (même ordre de sections, commentaires alignés, placeholders à la place des secrets). Le fichier exemple est la référence **structurelle** ; les vraies valeurs restent uniquement dans `lbg.env`.
- **Déploiement global / reproductibilité** : maintenir dans `bootstrap.md` (*Déploiement global initial*) et `architecture.md` (*Déploiement global final et reproductibilité*) la procédure pour recréer un serveur **vierge** équivalent ; tout changement de dépendance système, de chemin ou de port doit y être reflété (priorité 0).
- **Assistant local vs MMO** : toute évolution « agent bureau / mail / web ouvert » doit rester alignée avec **`docs/adr/0004-assistant-local-vs-persona-mmo.md`** (modes séparés, audit, drapeaux).
- Après chaque étape livrée (feature, correctif majeur, déploiement) : **court changelog** dans ce plan ou lien vers une section « État courant » (date + ce qui a bougé).
- Exemples opérationnels (commandes `curl`, flux d’appel backend ↔ orchestrateur) dès que les APIs stabilisent.

**Définition de « étape »** : incrément déployable ou mergé (local ou VM privée) qui modifie le comportement attendu par un opérateur ou un développeur.

---

## Priorité 1 — Orchestrateur, backend, agents, interface utilisateur

**Objectif** : chaîne complète **observable et pilotable** sur réseau privé — routage d’intentions, exécution via agents, visibilité santé et activité.

**Périmètre cible** :

1. **Orchestrateur** : registry des capacités, routage fiable, introspection, stratégies de fallback, traçabilité (logs structurés / corrélation des requêtes si pertinent).
2. **Backend** : API stable (contrats, erreurs), intégration orchestrateur, évolution sans casser les clients internes.
3. **Agents fonctionnels** : au moins un agent « classique » exécutant une tâche réelle (même minimale) derrière une capability déclarée ; traçabilité du résultat vers l’API ou les logs.
4. **Interface utilisateur (pilotage + monitoring)** : application dédiée (web ou autre selon décision d’implémentation) pour :
   - **piloter** : lancer / paramétrer des scénarios ou intentions de test, voir les réponses ;
   - **monitorer** : état des services, métriques ou health checks, journaux agrégés ou liens opérationnels.
5. **Architecture Événementielle (Cible)** : Transition vers un modèle piloté par événements (EDA) via un bus de messages (RabbitMQ/Kafka) pour découpler l'orchestrateur des agents et gérer les latences LLM via des **Circuit Breakers**.
6. **État du Monde (In-Memory)** : Utilisation de Redis pour un accès ultra-rapide à l'état transactionnel du multivers.
7. **Forge de prototypes OpenGame (expérimental)** : intégrer éventuellement OpenGame comme capability orchestrée (`agent.opengame`) pour générer des prototypes gameplay/UX dans une sandbox, sans donner à OpenGame l'autorité sur le projet ni modifier automatiquement le coeur MMO. Décision : `docs/adr/0003-opengame-forge-prototypes.md`.

Référence réseau : environnement **privé** ; toute exposition publique future = autre brique (voir `architecture.md`).

---

## Priorité 2 — Lyra

**Objectif** : tout ce qui relève de l’**IA incarnée** au sens projet : jauges, état comportemental, influence sur l’orchestration et/ou la simulation, et à terme présentation utilisateur riche (voir `lyra.md`).

**Périmètre indicatif** (à affiner avec `lyra.md`) :

- Modèle d’état Lyra (persistant ou session), validation côté services.
- Intégration avec l’orchestrateur et/ou le backend (contrats d’entrée/sortie).
- Évolution UI (contrôles, visualisation temps réel) en cohérence avec la Priorité 1 lorsque pertinent.

Cette priorité démarre lorsque le **noyau Priorité 1** permet de brancher Lyra sans ambiguïté sur le flux d’exécution.

---

## Priorité 3 — MMO

**Objectif** : serveur et systèmes de monde (entités, quêtes, factions, IA PNJ, etc.) conformément à la vision long terme (`plan_mmorpg.md`).

**Périmètre** :
1. **Stratégie Multi-Moteurs** : 
   - **Sandbox (OTServ/2D)** : Utilisation de serveurs Tibia-like pour les tests de charge IA massive (10k-30k PNJ) et la validation des comportements émergents.
   - **Cible (Ryzom Core/3D)** : Intégration finale sur moteur 3D pour le multivers complet.
2. **Pipeline Industriel PNJ** : 
   - Génération massive (30k+) via IA (Stable Diffusion/SDXL + ComfyUI) et rendu isométrique automatisé (Blender/Mixamo).
   - Schéma JSON unifié (Traits, Social, Visuel) piloté par l'orchestrateur.
3. **MJ IA (Game Master)** : IA capable de modifier l'environnement et de proposer des événements en temps réel.

---

## État courant (2026-04-27) — v1.1.1

| Composant | Statut | Notes |
|-----------|--------|-------|
| **Infrastructure Front** | **STABLE** | Unifié sur Port **8080** (VM 110). Lyra @ racine, client MMO servi sous la **route** `/mmo/`. Port 8081 supprimé. |
| **Explorateur Local** | **STABLE** | Synchronisation auto du build vers `LBG_IA_MMO/pilot_web/mmo/` via `deploy_web_client.sh`. |
| **Rendu Client** | **STABLE** | Assets en chemins **relatifs** ; robustesse aux sous-dossiers Nginx. |
| **Urbanisme** | **STABLE** | Échelle **16px/m** ; alignement bâtiments/PNJ corrigé sur `planet_map.png`. |
| **Physique Village** | **STABLE** | Collisions **SOLIDES** (hollow=False) sur les bâtiments ; marge ajustée (0.5). |
| **Monde MMO** | **STABLE** | Bouclage à ±51km (World Wrap) ; interpolation fluide client/serveur. |
| **Documentation** | **OK** | `architecture.md`, `fusion_env_lan.md`, `runbook` et `lexique` synchronisés. |

## Historique

| Date | Changement notoire |
|------|---------------------|
| 2026-05-02 | **Rang 1** : Pilot `#/desktop` — dictée navigateur (Web Speech API) + **Appliquer → notepad_append** ; doc `desktop_hybride.md`. **Rang 2+** : `memory_hint` (clés flags PNJ) + fusion `session_summary` **toujours** côté serveur même sans `ia_context` ; `dialogue_llm`, `mmmorpg_PROTOCOL`, tests `test_ia_context_sanitize`. **Client** : `web_client/README.md` (build, collisions village). **Branche** : merge `feature/comfyui-map-2pass-mmo` → `main`. |
| 2026-05-03 | **Rang 2+** : `session_summary` fusionné côté `mmmorpg_server` (quête joueur + PNJ ; client complète notes/humeur) ; clé `quest_snapshot` ; Pilot `#/desktop` champ résumé MMO + localStorage ; prompt desktop + PNJ ; tests sanitize enrichis. |
| 2026-05-03 | **Rang 2 (persona MMO)** : `lyra_engagement` forcé `mmo_persona` sur le pont WS ; `ia_context.session_summary` sanitisé ; paragraphes prompt dialogue + `meta.lyra_engagement_resolved` ; client `web_client` envoie `session_summary` (quête + PNJ) ; tests `test_lyra_engagement_prompt`, `test_ia_context_sanitize` ; `lyra.md`, `mmmorpg_PROTOCOL`. |
| 2026-05-03 | **Desktop rang 1 — IMAP aperçu** : action `mail_imap_preview` (filtres `from_contains` / `subject_contains`, extraits de corps bornés, INBOX lecture seule) ; module `mail_imap_preview.py` (agents + workers) ; env `LBG_DESKTOP_MAIL_*` / `LBG_LINUX_MAIL_*` ; prompt `DESKTOP_JSON` ; doc `desktop_hybride.md` / `agents/README` ; tests `test_desktop_mail_imap`. |
| 2026-05-03 | **Desktop rang 1 — recherche web bornée** : action `search_web_open` (`query`) dans `desktop_executor`, workers Windows/Linux, sanitize `dialogue_llm`, dry-run / approval / audit alignés `open_url` ; opt-in `LBG_DESKTOP_WEB_SEARCH` / `LBG_LINUX_WEB_SEARCH`, moteur `LBG_*_SEARCH_ENGINE` (DDG ou Google) ; doc `desktop_hybride.md`, `agents/README`, tests `test_desktop_search_web`. |
| 2026-05-03 | **Commit inventaire (session)** : flags `player_item_id` + `player_item_qty_delta` (+ `player_item_label`) ; `player_id` JSON sur `POST …/dialogue-commit` ; ordre **validation puis idempotence** sur `trace_id` ; fusion NPC **sans** `player_item_*` dans `world_flags` ; `/v1/pilot/route` → `try_commit_dialogue(..., player_id)` depuis `actor_id` `player:<uuid>` ou `context` ; tests `test_player_inventory`, `test_internal_http_dialogue_commit_player_inventory` ; `mmmorpg_PROTOCOL`, `mmmorpg_server/README`. |
| 2026-05-03 | **Étoile du nord (Boîte à idées)** : prise en compte prioritaire de `Boite à idées/20260428_1220_on ce recentre.txt` — ordre **poste/infra → MMO/apprentissage → évolution monde contrôlée** ; tableau *Fil produit* + section *Étoile du nord produit* dans `plan_de_route.md` ; `vision_projet.md` (objectif premier recentré). |
| 2026-05-03 | **Carte plan global** : `docs/carte_plan_global.md` (alignement items `.cursor/rules` ↔ monorepo, backlog explicite) ; `README.md` : `mmmorpg_server/`, `web_client/`. |
| 2026-05-03 | **Inventaire joueur v1 (session)** : `stats.inventory` (liste `{ item_id, qty, label }`) — sac de départ côté `mmmorpg_server` (`GameState.add_player` / fusion stats au `move` sans écraser l’inventaire) ; fiche voyageur **Sac (session)** dans `web_client` ; test `test_player_inventory` ; doc `mmmorpg_PROTOCOL`. |
| 2026-05-03 | **Dispatch dialogue** : `output.dialogue_profile_resolved` (miroir de `remote.meta`) pour Pilot / traces ; doc `agents/README` ; test `test_dispatch_dialogue`. |
| 2026-05-02 | **Client MMO — bulle : plafond lignes** : garde-fou visuel `Renderer.MAX_BUBBLE_BODY_LINES` (troncature avec ellipse) pour répliques LLM très longues (`renderer.js`). |
| 2026-05-02 | **Pilot** : affichage `remote.meta.dialogue_profile_resolved` (chat) ; `pilot_web/README` (invoke proxy, profil résolu) ; `lbg.env.example` — laisser `LBG_ORCHESTRATOR_DIALOGUE_PROFILE_DEFAULT` vide pour prioriser le `tone` du registre PNJ ; test `POST /v1/pilot/agent-dialogue/invoke`. |
| 2026-05-02 | **Agent dialogue — alias ``tone`` registre + méta invoke** : `REGISTRY_TONE_ALIASES` (ex. `pragmatique`→`professionnel`, `direct`→`mini-moi`) ; réponse `POST /invoke` → `meta.dialogue_profile_resolved`. |
| 2026-05-02 | **Agent dialogue — profil depuis registre PNJ** : si ``context.dialogue_profile`` est absent, le champ ``tone`` de l’entrée ``npc_registry.json`` (clé = ``world_npc_id``) est utilisé quand il correspond à un profil connu ; la clé de cache LLM inclut le profil résolu (``pf=…``). |
| 2026-05-02 | **Agent dialogue — profils PNJ (MMO)** : parité des clés `dialogue_profile` avec l’assistant (`hal`, `test`, etc.) + constante `MMO_PROFILE_TEMPLATES` dans `dialogue_llm` (suffixe `BASE_GUARDRAILS_MMO` inchangé). |
| 2026-05-02 | **Client MMO — bulles riches** : sous-titre de rôle PNJ (`entities[].role`, masqué pour `civil` / `player`), état d’attente avec écho du message joueur, corps des répliques PNJ wrap plus large (≈ 42×12) ; sources `web_client` `main.js`, `renderer.js`, build `dist`. |
| 2026-05-02 | **Dialogue multi‑LLM + suivi** : `dialogue_target=auto`, `LBG_DIALOGUE_AUTO_ORDER`, budget soft `LBG_DIALOGUE_BUDGET_MAX_USD` (mode auto), coût estimé `fast`, traces enrichies (`latency_ms`, `outcome`, `player_text_preview`, `invoke_actor_id`, décision route) ; `GET /healthz` expose `dialogue_budget` ; orchestrateur accepte `LBG_ORCHESTRATOR_DIALOGUE_TARGET_DEFAULT=auto`. Doc `agents/README`, `lbg.env.example`, tests. |
| 2026-05-02 | **Pilot desktop — bandeau config** : `GET /healthz` agent dialogue expose `desktop_plan_env_enabled` ; page `#/desktop` interroge `GET /v1/pilot/status` pour guider LLM + `LBG_DIALOGUE_DESKTOP_PLAN` ; doc `agents/README.md`, `lbg.env.example`, `desktop_hybride.md`. |
| 2026-05-02 | **Pilot desktop — proposition LLM** : `DESKTOP_JSON` dans `dialogue_llm` (env `LBG_DIALOGUE_DESKTOP_PLAN` + `context._desktop_plan`), `meta.desktop_action_proposal` sur l’agent HTTP, proxy `POST /v1/pilot/agent-dialogue/invoke`, bouton *Proposer via IA* dans `#/desktop` ; doc `desktop_hybride.md`. |
| 2026-05-05 | **ADR 0004 (màj)** : aligné sur l’existant **`desktop_control`** / **`agent.desktop`** / worker **`windows_agent`·`linux_agent`** ; commentaires `lbg.env.example` ; renvoi depuis `desktop_hybride.md`. |
| 2026-05-05 | **ADR 0004** : assistant poste (`local_assistant`) vs persona MMO (`mmo_persona`) — périmètres, routage, audit, lien doux session→assistant, aligné vision Boîte à idées. Renvoi depuis `lyra.md`. |
| 2026-05-04 | **Tests / déploiement MMO** : `bootstrap.md` — pytest ciblé avec **uv** depuis `LBG_IA_MMO/`. `deploy_web_client.sh` : **`LBG_MMO_WEB_DEPLOY_LOCAL_ONLY=1`** (build `--base=/mmo/` + `pilot_web/mmo/` sans SSH). `.gitignore` : `uv.lock` sous agents/backend/mmmorpg_server. Doc `architecture`, `runbook`. Sync **`pilot_web/mmo`** + `web_client/dist` alignés. |
| 2026-05-03 | **Client MMO — libellés races (catalogue)** : `GET /world-content` enrichi (`race_display` id → nom) ; client `web_client` charge pilot/agent (same-origin / ports 8080·8000·8020) ; **fiches rafraîchies en async** après `welcome`. Doc `agents/README`, `mmmorpg_PROTOCOL`, `plan_de_route`. |
| 2026-05-02 | **Client MMO — fiches personnage (joueur + PNJ)** : HUD *Fiche voyageur* et *Fiche PNJ* (`web_client`) ; doc `docs/mmmorpg_PROTOCOL.md` (*HUD client MMO — fiches personnage*). Build `dist` à jour. |
| 2026-05-02 | **Client MMO — synchro `stats.quest_state`** : après `welcome` et chaque `world_tick`, le journal / quête suivie se réalignent sur `entities[].stats.quest_state` du joueur courant ; build `web_client` + doc `docs/mmmorpg_PROTOCOL.md` (paragraphe client). |
| 2026-05-03 | **MMO WS — quête joueur (session)** : `commit_dialogue` accepte `player_id` et met à jour `stats.quest_state` sur le joueur si les `flags` contiennent des champs quête (pont IA + `move.world_commit`). État **volatile** (pas de persistance disque). Doc : `docs/mmmorpg_PROTOCOL.md`. |
| 2026-05-03 | **Catalogue monde (races + bestiaire)** : fichiers `LBG_IA_MMO/content/world/races.json` et `creatures.json` ; injection prompt dialogue (`race_id`, `context._creature_refs`) ; snapshot Lyra (`meta.race_id`, `meta.race_display`) côté `mmmorpg_server` ; agent dialogue `GET /world-content` ; proxy pilot `GET /v1/pilot/agent-dialogue/world-content` ; UI `/pilot/` (*Charger world-content*). Variable optionnelle `LBG_WORLD_CONTENT_DIR`. **Suite — continuité doc** : section *Fil produit ↔ documentation* dans ce plan ; paragraphe *Catalogue monde* dans `architecture.md` ; exemples `curl` npc-registry / world-content dans `bootstrap.md` ; section env catalogue dans `lbg.env.example` ; renvoi opérationnel dans `plan_mmorpg.md`. |
| 2026-05-02 | **Quêtes — réputation sur ACTION_JSON quest** : `reputation_delta` optionnel (entier ±100) dans la même ligne `kind:"quest"` ; sanitisation agent, commit HTTP, application serveur existante (`reputation_delta` dans les flags). |
| 2026-05-02 | **Client MMO — quête suivie dans tout le chat** : si une quête est suivie dans le HUD, `_active_quest_id` est fusionné automatiquement dans `ia_context` pour chaque message PNJ (sans écraser une valeur déjà fournie), pour aligner dialogue libre et boutons rapides. |
| 2026-05-02 | **Quêtes — clôture monde (`quest_completed`)** : whitelist serveur + ACTION_JSON dialogue + commit agent + `world_event` « Quête accomplie » ; contexte `_active_quest_id` vers l’IA ; HUD « TERMINER QUÊTE » ; journal local et état PNJ affichent la clôture. **Mouvement client** : offset sprite stable (plus de flip selon position), bobbing et lissage positions/caméra adoucis. |
| 2026-05-02 | **MMO — persistance immédiate des actions monde** : les commits dialogue acceptés (`world_commit` direct ou action IA PNJ) déclenchent désormais une sauvegarde JSON immédiate de l’état serveur persistant (`seen_trace_ids`, flags PNJ, réputation, jauges), en plus de la sauvegarde à l’arrêt propre. Test ciblé `test_persistence` ajouté. |
| 2026-05-02 | **Client MMO — quête suivie locale** : le journal de quêtes devient actionnable côté HUD : clic/clavier sur une quête pour la suivre, résumé “Quête suivie” dans le panneau joueur, persistance `localStorage`, et reset lors du vidage du journal. Build + déploiement `/mmo/` validés. |
| 2026-05-02 | **Client MMO — état PNJ ciblé** : les snapshots PNJ exposent `world_state` (`reputation`, jauges faim/soif/fatigue, flags monde) et le HUD affiche l’état de la cible courante, pour rendre les effets des dialogues persistants visibles au joueur. |
| 2026-05-02 | **Client MMO — journal Actions IA** : les `world_event.dialogue_commit` alimentent désormais un panneau HUD “Actions IA” côté client, avec déduplication par `trace_id`, distinction aide/quêtes, et bulle d’action temporaire au-dessus du PNJ. |
| 2026-05-02 | **Dialogue PNJ → action monde v1** : le pont WS applique désormais les `commit` bornés renvoyés par l’agent dialogue (`aid`/`quest`) via `GameState.commit_dialogue`, avec garde-fou d’autorité serveur : l’action ne peut viser que le PNJ ciblé par la conversation. Le `world_tick` peut exposer `world_event` pour feedback client. Tests ciblés `mmmorpg_server` OK. |
| 2026-05-01 | **Dialogue PNJ — placeholder nommé + route rapide** : le placeholder WS remplace `Le PNJ` par le nom réel (`{npc_name}`), l’orchestrateur injecte `dialogue_target=fast` par défaut sur `agent.dialogue`, et `dialogue_llm` résout `fast` vers un provider rapide OpenAI-compatible (`LBG_DIALOGUE_FAST_*`) avec fallback remote/local. |
| 2026-05-01 | **Client MMO — régression corrigée** : le build Vite avait réintroduit l’ancien rendu isométrique ; `web_client/src/renderer.js` est réaligné sur le rendu top-down stable (caméra joueur, zoom, `planet_map`, `bourg_palette_map`) avec bulles/sélection PNJ intégrées. Déploiement front `/mmo/` validé sur `index-C_pLjWcn.js` + garde-fou anti-régression dans `deploy_web_client.sh`. |
| 2026-05-01 | **MMO — pause conversation PNJ** : quand le pont WS→IA démarre une conversation, le PNJ visé s’arrête et se tourne vers le joueur ; à la réponse finale ou en cas d’échec IA, son `busy_timer` est remis à **120s** avant reprise de sa routine. Tests `mmmorpg_server` OK. |
| 2026-05-01 | **Client MMO — bulles de dialogue v1** : le chat cible désormais le PNJ sélectionné au clic ou, à défaut, le PNJ le plus proche ; conserve la position courante lors de l’envoi WS ; affiche une bulle “en attente” puis remplace par la réponse `npc_reply` du pont IA ; HUD enrichi avec la cible de dialogue courante. |
| 2026-05-01 | **OpenGame — exécution contrôlée** : `agent.opengame` peut lancer la CLI **uniquement** si `LBG_OPENGAME_DRY_RUN=0` + `LBG_OPENGAME_EXECUTION_ENABLED=1` (+ approval optionnelle) ; exécution sans `--yolo`, dossier cible vide obligatoire, timeout/capture stdout-stderr, audit JSONL. |
| 2026-05-01 | **OpenGame — squelette agent** : ajout de la capability **`prototype_game`** → **`agent.opengame`** ; action structurée `context.opengame_action.kind=generate_prototype`, dry-run par défaut, sandbox `LBG_OPENGAME_SANDBOX_DIR`, audit `agents.opengame.audit`, tests dispatch/routage/classifieur. |
| 2026-05-01 | **ADR 0003 OpenGame** : décision d'intégrer OpenGame uniquement comme forge de prototypes orchestrée (`agent.opengame` cible), sandboxée, auditée, avec promotion manuelle vers le MMO ; l'orchestrateur reste le maître d'orchestre du projet. |
| 2026-04-09 | Création du plan de route ; squelette backend / orchestrateur / mmo_server en place ; déploiement systemd sur VM privée documenté ; règle réseau inscrite dans `architecture.md`. |
| 2026-04-09 | Procédure **dev → prod** formalisée (`deploy_vm.sh`, contrôles, doc) dans `bootstrap.md`, `architecture.md` et Priorité 0 de ce plan. |
| 2026-04-09 | Finalité **déploiement global reproductible** (serveur vierge, sources de vérité, pistes d’industrialisation) dans `architecture.md` + checklist dans `bootstrap.md`. |
| 2026-04-09 | Exemples **`curl`** backend + orchestrator (intentions) ajoutés dans `bootstrap.md` (*Exemple API*) ; flux bout-en-bout documenté. |
| 2026-04-09 | **`pilot_web/`** + route **`GET /v1/pilot/status`** (santé agrégée) + page **`/pilot/`** ; doc `README`, `bootstrap`. |
| 2026-04-09 | Paquet **`agents/`** (`lbg_agents.dispatch`) branché sur **`POST /v1/route`** ; `install_local.sh` + image Docker orchestrator mises à jour. |
| 2026-04-09 | **`GET /v1/capabilities`** (orchestrator) + proxy **`GET /v1/pilot/capabilities`** (backend) + tableau sur **`/pilot/`**. |
| 2026-04-09 | **Agent HTTP dialogue** (`lbg_agents.dialogue_http_app`, port 8020), `LBG_AGENT_DIALOGUE_URL`, unité **`lbg-agent-dialogue`**, orchestrator mis à jour, `deploy_vm` active 4 services. |
| 2026-04-10 | Chaîne dialogue stabilisée : timeout backend → orchestrator configurable (`LBG_ORCHESTRATOR_TIMEOUT`) ; agent dialogue optimise Ollama via `POST /api/chat` (keep-alive + limite de tokens) + prompt plus court ; UI `/pilot/` affiche aussi le `llm_model`. |
| 2026-04-10 | “Prod prévisible” : modèle dialogue par défaut fixé sur `phi4-mini:latest` ; `LBG_DIALOGUE_LLM_MAX_TOKENS` autorise des valeurs très basses (ex. 24) ; doc variables perf alignée dans `agents/README.md`. |
| 2026-04-10 | Variables “performance” appliquées sur la VM privée (`/etc/lbg-ia-mmo.env`) ; redémarrage systemd ; checks `curl` + UI `/pilot/` validés. |
| 2026-04-10 | Pilot web : ajout d’un endpoint timé (`POST /v1/pilot/route` → `elapsed_ms`) + benchmark N requêtes (p50/p95) ; cible VM fixée p50 < 2000ms, p95 < 6000ms. |
| 2026-04-10 | Benchmark VM (N=10) : min=10972ms, p50=14194ms, p95=15547ms, max=15547ms — **cible non atteinte** (p50<2000ms, p95<6000ms). |
| 2026-04-10 | Latence acceptée “pour le moment” : benchmark conservé comme outil de constat ; optimisation latence reportée. |
| 2026-04-10 | Routage : si `context.npc_name` est présent, intent forcé `npc_dialogue` (dialogue systématique). |
| 2026-04-10 | Agent `agent.quests` : handler stub structuré (objet `quest`) + preset “Quête” dans `/pilot/` pour tester la capability `quest_request`. |
| 2026-04-10 | Pilot web : affichage lisible (`reply`/`quest`) + bouton “Copier JSON” + auto-history multi-tours par `npc_name`. |
| 2026-04-10 | Pilot/backend : ajout `trace_id` (propagé via `context._trace_id`) et affiché dans `/pilot/` pour corrélation. |
| 2026-04-10 | Logs : `trace_id` journalisé côté orchestrator (`event=orchestrator.route`) et dispatch agents (`event=agents.dispatch`) en JSON. |
| 2026-04-28 | Desktop “hybride” : nouvelle capability **`desktop_control`** → `agent.desktop` + worker HTTP Windows (module `windows_agent/Agent_IA`, `C:\\Agent_IA`, endpoints `/healthz` + `/invoke`) avec allowlists/dry-run/approval/audit ; UI pilot : ajout de la vue **`#/desktop`** (sync texte↔JSON + presets). Doc : `docs/desktop_hybride.md`. |
| 2026-04-28 | Rangement : le worker Windows **Agent_IA** est traité comme un module du repo (`windows_agent/Agent_IA`) + script WSL de sync vers `C:\\Agent_IA` : `infra/scripts/sync_windows_agent.sh`. |
| 2026-04-28 | Ajout module Linux `linux_agent/Agent_IA` (worker HTTP, `linux.env` hot-reload, allowlists/dry-run/approval/audit, actions `open_url`/`file_append`/`open_app` + learn) + script de sync VM `infra/scripts/sync_linux_agent_vm.sh` (à pousser plus tard). |
| 2026-04-28 | Orchestrateur : ajout d’un **Brain (autonomie) v1** (tick **30s**) avec **conscience** (`gauges`) + **motivation** (`intent`, `narrative`) + file `approval_requests[]`. Endpoints `GET /v1/brain/status`, `POST /v1/brain/toggle`, `POST /v1/brain/approve` ; exécute `selfcheck` (safe, dry-run) + pings `healthz` ; `systemd_restart` uniquement en opt-in + jeton (`LBG_BRAIN_DEVOPS_*`) + approval. UI : panneau “Brain” dans `#/ops` via proxy backend. Doc : `docs/architecture.md`. |
| 2026-04-10 | Routage : `npc_name` force `npc_dialogue` seulement si le texte ne déclenche pas déjà une intention (ex. `quest_request`). Preset `/pilot/` “Quête (PNJ)”. |
| 2026-04-10 | Quêtes : `agent.quests` enrichi avec `quest_state` (quest_id/status/step) + preset `/pilot/` “Avancement quête” pour simuler un 2ᵉ appel. |
| 2026-04-10 | Pilot web : persistance client de `quest_state` (par `npc_name`/global) et réinjection automatique dans `context` pour le flux “quête → avancement”. |
| 2026-04-10 | Agent `agent.quests` : service HTTP optionnel (`lbg_agents.quests_http_app`, port 8030) + variable `LBG_AGENT_QUESTS_URL` + unité systemd `lbg-agent-quests.service`. |
| 2026-04-10 | Pilot status : santé agrégée quests via `LBG_AGENT_QUESTS_URL` (healthz) + déploiement VM active `lbg-agent-quests`. |
| 2026-04-10 | Backend : proxy same-origin `GET /v1/pilot/agent-dialogue/healthz` et `GET /v1/pilot/agent-quests/healthz` ; `/pilot/` utilise ces liens (plus besoin d’ouvrir 8020/8030 côté client). |
| 2026-04-10 | Agent `agent.combat` : service HTTP optionnel (`lbg_agents.combat_http_app`, port 8040) + `LBG_AGENT_COMBAT_URL` + unité `lbg-agent-combat.service` ; pilot status + proxy `agent-combat/healthz` ; quêtes HTTP : `POST /invoke` appelle `run_quests_stub` (évite récursion si même `lbg.env`). |
| 2026-04-10 | **`devops_probe` / `agent.devops`** : exécuteur à liste blanche (`http_get` sur URLs autorisées, `read_log_tail` si chemins autorisés) ; routage forcé si `context.devops_action` ; preset `/pilot/` « DevOps (sonde) ». |
| 2026-04-10 | DevOps : **`LBG_DEVOPS_DRY_RUN`** (global) + `context.devops_dry_run` ; journal d’audit JSON **`agents.devops.audit`** sur stdout ; case dry-run dans `/pilot/`. |
| 2026-04-10 | DevOps : **`LBG_DEVOPS_APPROVAL_TOKEN`** + `context.devops_approval` pour toute exécution réelle (hors dry-run) ; audit `approval_denied` / `approval_gate_active`. |
| 2026-04-10 | DevOps audit : **`LBG_DEVOPS_AUDIT_LOG_PATH`** (JSONL append, `ts` UTC), **`LBG_DEVOPS_AUDIT_STDOUT`** pour couper stdout si besoin. |
| 2026-04-10 | Ops : **`docs/ops_devops_audit.md`** (rotation jeton, logrotate) + **`infra/logrotate/lbg-devops-audit`**. |
| 2026-04-10 | VM : compte **`lbg`** (sudoer + SSH) ; systemd **`User=lbg`/`Group=lbg`** ; `deploy_vm.sh` / `push_secrets` (640 root:lbg) ; **`docs/ops_vm_user.md`**. |
| 2026-04-10 | Combat : stub poursuivi via **`context.encounter_state`** (tours / PV / statuts terminal) ; réponse **`encounter` + `encounter_state`** ; `/pilot/` persistance locale + preset **« Avancement combat »** (clé par adversaire ou `global`). |
| 2026-04-10 | Lyra : **contrat brouillon** `context.lyra` / `output.lyra` dans **`lyra.md`** ; point d’accroche orchestrateur ↔ Lyra dans **`architecture.md`**. |
| 2026-04-10 | **`/pilot/`** : affichage lecture seule de **`output.lyra`** (JSON) lorsque présent dans la réponse agent. |
| 2026-04-10 | Lyra : echo minimal — **`context.lyra` → `output.lyra`** via stub **`agent.fallback`** (`minimal_stub` / `_echo` dans `dispatch`). |
| 2026-04-10 | Lyra : **`lbg_agents.lyra_bridge`** — pas de jauges **`hunger`/`thirst`/`fatigue`** via `lyra_engine.gauges` quand **`mmo_server`** est installé ; preset `/pilot/` **Lyra (test)** aligné sur ce schéma. |
| 2026-04-10 | Lyra : **`agent.dialogue`** (HTTP) — `step_context_lyra_once` avant `POST /invoke`, **`output.lyra`** renvoyé + contexte mis à jour pour le LLM. |
| 2026-04-10 | Lyra : **`dialogue_llm.build_system_prompt`** — résumé **`context.lyra.gauges`** (faim/soif/fatigue, etc.) + consigne de ton pour le LLM. |
| 2026-04-11 | **Persistance `WorldState`** : JSON atomique (`mmo_server/world/persistence.py`), chargement au boot + sauvegarde périodique + à l’arrêt ; verrou **`world_lock`** ; variables **`LBG_MMO_STATE_PATH`**, **`LBG_MMO_SAVE_INTERVAL_S`**, **`LBG_MMO_DISABLE_PERSIST`** ; défaut `mmo_server/data/world_state.json` (fichier **créé au runtime** au premier run). |
| 2026-04-11 | **Boucle monde → Lyra** : `mmo_server` expose **HTTP** (`http_app`, uvicorn **8050**) avec tick en arrière-plan et **`GET /v1/world/lyra`** ; backend **`merge_mmo_lyra_if_configured`** si **`LBG_MMO_SERVER_URL`** + **`context.world_npc_id`** ; **`lyra_bridge`** ignore le pas moteur si **`meta.source` = `mmo_world`** ; pilot **status** + proxy **`/v1/pilot/mmo-server/healthz`** ; preset **Lyra + monde (MMO)** ; systemd **`lbg-mmo-server`** bascule sur uvicorn. |
| 2026-04-11 | **Plan de fusion LBG_IA ↔ MMO** : ajout de **`docs/plan_fusion_lbg_ia.md`** (principes, correspondances agents/Lyra/monde, matrice de décision tronc, phases A–E, risques). |
| 2026-04-11 | **mmmorpg** intégré au plan de fusion : dépôt **`~/projects/mmmorpg`** (WebSocket, `PROTOCOL.md`) distingué de **`mmo_server`** (HTTP Lyra) ; §3.4 et phases A–C du **`plan_fusion_lbg_ia.md`** mises à jour. |
| 2026-04-11 | **Topologie prod LAN** documentée dans **`plan_fusion_lbg_ia.md`** : **0.140** LBG_IA_MMO, **0.110** LBG_IA, **0.245** mmmorpg ; stratégie **serveurs distincts** vs **regroupement** de fonctions. |
| 2026-04-11 | **Répartition 1 / 2 / 3 machines** + périmètre **`deploy_vm.sh`** (LBG_IA_MMO uniquement) dans **`plan_fusion_lbg_ia.md`** ; phase A fusion **ouverte**. |
| 2026-04-11 | **Point 1 (phase A)** : **`docs/fusion_env_lan.md`** — **140** orchestration + LBG_IA, **245** MMO (`mmmorpg` + `mmo_server`), **110** LLM (+ modules ; **option** front) ; table **`LBG_MMO_SERVER_URL`**, **`LBG_DIALOGUE_LLM_*`**. |
| 2026-04-11 | **`fusion_env_lan.md`** : schéma Mermaid 140↔110↔245 ; compte **`lbg` sudoer** sur 3 VM ; **`deploy_vm.sh`** multi-cible (`LBG_VM_HOST`) ; entête script mise à jour. |
| 2026-04-11 | **`deploy_vm.sh` par rôles** : `LBG_DEPLOY_ROLE` **`core` \| `mmo` \| `front` \| `all`** — **core** sur **140** sans `mmo_server/` (`LBG_SKIP_MMO_SERVER=1`, `pilot_web` exclu si `LBG_PILOT_WEB_ON_FRONT=1`), **mmo** sur **245** (`install_local_mmo.sh`, `lbg-mmo-server` seul), **front** sur **110** (uniquement `pilot_web/`). Mode **`all`** : séquence **140 → 245 → 110** ; `LBG_PUSH_SECRETS` une fois vers le core si activé. |
| 2026-04-11 | **Déploiement LAN validé** : compte **`lbg`** sur **140 / 245 / 110** ; `LBG_DEPLOY_ROLE=all bash infra/scripts/deploy_vm.sh` exécuté avec succès (core sans slice MMO sur 140, MMO sur 245, statique pilot sur 110). **Note** : un premier `deploy_vm.sh` sans `all` sur 140 peut encore avoir installé **`mmo_server`** sur le core (comportement ancien / rôle `core` non forcé). |
| 2026-04-12 | **Fusion** : décision documentée — **tronc unique** = monorepo **`LBG_IA_MMO/`** ; **`LBG_IA`** et **`mmmorpg`** **non modifiés** (reproduction / intégration ici) ; **cible** : **un repo**, **trois machines**, projet **cohérent** (`plan_fusion_lbg_ia.md`). |
| 2026-04-12 | **ADR** **`docs/adr/0001-tronc-monorepo.md`** : tronc monorepo, sources en lecture ; checklist phase A (ADR tronc) cochée dans `plan_fusion_lbg_ia.md`. |
| 2026-04-12 | **`docs/lexique.md`** : lexique projet (définition **ADR**, termes transverses) pour faciliter la transmission ; référencé depuis priorité 0 et documents liés. |
| 2026-04-12 | **Fusion phase A** : **`docs/fusion_etat_des_lieux_v0.md`** (routes OpenAPI monorepo, ref **`LBG_IA/.../HTTP_ROUTES.md`**, synthèse **mmmorpg**) ; fin de phase A doc sauf sous-ADR. |
| 2026-04-12 | **ADR 0002** + **seed monde** : `docs/adr/0002-mmo-autorite-pont.md` ; PNJ initiaux dans **`mmo_server/world/seed_data/`** (`world_initial.json`, `LBG_MMO_SEED_PATH`). |
| 2026-04-12 | **Phase B fusion** : **`fusion_spec_lyra.md`**, **`fusion_spec_agents.md`**, **`fusion_spec_monde.md`**, **`fusion_pont_jeu_ia.md`** — specs Lyra / agents / monde / pont. |
| 2026-04-12 | **Phase C** : script **`verify_stack_local.sh`**, test chaîne **`pilot` + `world_npc_id` + merge Lyra** ; **`bootstrap.md`** mis à jour. |
| 2026-04-12 | **`mmmorpg_server/`** (port WS) + **`docs/mmmorpg_PROTOCOL.md`** ; tests **`test_pilot_route_devops_trace.py`** ; install **`LBG_SKIP_MMMORPG_WS`**. |
| 2026-04-12 | **systemd** **`lbg-mmmorpg-ws`** + **`deploy_vm.sh` / `push_secrets_vm.sh`** (redémarrages conditionnels). |
| 2026-04-12 | **Prod LAN** : **`LBG_CORS_ORIGINS`** (`backend/main.py`), Nginx **`infra/scripts/install_nginx_pilot_110.sh`** + **`infra/nginx/pilot_web_110.conf.example`**, smoke **`infra/scripts/smoke_vm_lan.sh`** ; tests **`test_cors.py`**. |
| 2026-04-12 | **Reprise LAN (fin de session)** : env **`lbg.env`** avec **IP 140** pour agents/orchestrateur ; **`push_secrets_vm.sh`** vers **les 3 VM** ; **`smoke_vm_lan.sh`** vert (core + MMO + Ollama) ; clés SSH **`lbg`** sur **140 / 245 / 110** ; **`deploy_vm.sh` `all`** validé ; conflit **:80** sur **110** documenté (**Traefik** `orchestrateur-traefik` LBG_IA) → nginx pilot via **`LBG_NGINX_PILOT_PORT=8080`** + **`LBG_CORS_ORIGINS`** (`fusion_env_lan.md`, `ops_vm_user.md`). |
| 2026-04-13 | **Pilot front (110)** : Nginx proxifie **`/v1/*` → 140:8000** (`infra/nginx/pilot_web_110.conf.example`) ; astuce UI dans `pilot_web/index.html` (URL backend vide si même origine). |
| 2026-04-13 | **Ollama (110) LAN** : exposition **`OLLAMA_HOST=0.0.0.0:11434`** pour accès depuis **140** ; alignement `LBG_DIALOGUE_LLM_BASE_URL` en **`…/v1`** dans `infra/secrets/lbg.env`. |
| 2026-04-13 | **Pont jeu → IA (WS)** : `mmmorpg_server` appelle **`POST /v1/pilot/route`** depuis **245** via **`MMMORPG_IA_BACKEND_URL`** ; fiabilisation **placeholder** (`MMMORPG_IA_PLACEHOLDER_*`) + timeout **`MMMORPG_IA_TIMEOUT_S`** ; pont aussi sur **`move`** (champs optionnels) — doc `docs/mmmorpg_PROTOCOL.md`. |
| 2026-04-13 | **CLI benchmark** : `mmmorpg_server/tools/ws_ia_cli.py` (repeat/p95 + `--final-only`) ; smoke LAN + bench **final-only** OK (latence LLM élevée mais stable sur échantillon). |
| 2026-04-14 | **Réconciliation IA → jeu (phase 2)** : `mmmorpg_server` filtre/persiste les `flags` (liste blanche) ; snapshot expose `meta.world_flags` ; smoke E2E LAN `infra/scripts/smoke_commit_dialogue.sh`. |
| 2026-04-15 | **Pont jeu → IA (durcissement)** : ajout d’un endpoint service→service **`POST /v1/pilot/internal/route`** (token optionnel `X-LBG-Service-Token` + rate-limit best-effort) ; `mmmorpg_server` pointe par défaut sur `MMMORPG_IA_BACKEND_PATH=/v1/pilot/internal/route` et propage `X-LBG-Trace-Id` pour corrélation. |
| 2026-04-15 | **Ops** : `sudoers` NOPASSWD à liste blanche (user `lbg`) sur 140/245/110 ; scripts `deploy_vm.sh` et `push_secrets_vm.sh` n’utilisent plus `sudo -v` (plus de prompt interactif) ; smokes `smoke_commit_dialogue.sh` et `smoke_bridge_ws_lyra.sh` validés. |
| 2026-04-15 | **Dialogue** : cache + “réponses courtes strictes” activés ; observabilité cache (`cache_hit`, stats healthz + par speaker) ; endpoint admin `POST :8020/admin/cache/reset` (token optionnel `LBG_DIALOGUE_ADMIN_TOKEN`) ; UI `/pilot/` : toggle `No cache` + stats p50/p95 hit/miss. |
| 2026-04-15 | **Pont WS→Lyra (HTTP interne)** : token `MMMORPG_INTERNAL_HTTP_TOKEN` + rate-limit `MMMORPG_INTERNAL_HTTP_RL_*` activés ; backend consomme via `LBG_MMMORPG_INTERNAL_HTTP_TOKEN` ; smokes mis à jour (auto-token depuis `infra/secrets/lbg.env`) et revalidés. |
| 2026-04-15 | **Réconciliation IA→jeu** : validation flags durcie côté `mmmorpg_server` (bornes simples) ; pré-filtrage best-effort côté backend ; nouveau smoke rejet `infra/scripts/smoke_commit_reject_flag.sh` (attend 409 + reason). |
| 2026-04-15 | **Pont interne** : validation “prod LAN” confirmée via `ws_ia_cli.py --final-only` (réponse finale reçue, `trace_id` présent) + smokes verts. |
| 2026-04-15 | **Observabilité pont WS→IA** : logs corrélés `trace_id` côté `mmmorpg_server` + backend `/v1/pilot/internal/route` ; smoke LAN `infra/scripts/smoke_ws_ia_final_only_json.sh` (ws_ia_cli final-only JSON) ajouté et validé. |
| 2026-04-15 | **Données monde v1** : seed `mmo_server/world/seed_data/world_initial.json` enrichi (PNJ `npc:innkeeper`, `npc:guard`, `npc:scribe`) + validation via `/v1/world/lyra` sur la VM MMO (reset état persisté pour recharger le seed). |
| 2026-04-15 | **Pilot / NPC v1** : UI `/pilot/` enrichie (chips `world_npc_id` + preset “Scribe”) ; validation dialogue complet sur `npc:innkeeper` via `/v1/pilot/route` et `ws_ia_cli.py --final-only` ; déploiement front (110). |
| 2026-04-15 | **Snapshot WS interne (durcissement)** : smoke LAN `infra/scripts/smoke_snapshot_auth_rl.sh` (401 sans token, 200 avec token, 429 si RL activé) ajouté et validé. |
| 2026-04-16 | **Fallback lecture monde** : `lbg-mmo-server` écoute **`0.0.0.0:8050`** (LAN) + smoke LAN `infra/scripts/smoke_merge_lyra_snapshot_fallback_lan.sh` (snapshot interne forcé KO → `meta.source=mmo_world`). |
| 2026-04-16 | **LAN — post `LBG_DEPLOY_ROLE=all`** : smokes verts `smoke_merge_lyra_snapshot_fallback_lan.sh`, `smoke_pilot_route_lyra_meta_lan.sh` (nouveau), `smoke_bridge_ws_lyra.sh`, `smoke_commit_dialogue.sh`, `smoke_commit_reject_flag.sh` ; **régression** : `smoke_ws_ia_final_only_json.sh` / `ws_ia_cli` peut **timeouter** sans `npc_reply` final (pont WS→IA à investiguer : `lbg-mmmorpg-ws`, token backend, orchestrateur). |
| 2026-04-16 | **Pont WS→IA (fiabilité)** : augmentation `MMMORPG_IA_TIMEOUT_S` sur **245** (service `lbg-mmmorpg-ws`) ; `infra/scripts/smoke_ws_ia_final_only_json.sh` revalidé (stress) **sans timeouts** ; latence infra/LLM toujours élevée mais acceptée “pour le moment”. |
| 2026-04-16 | **Pilot route (observabilité Lyra)** : `POST /v1/pilot/route` expose `lyra_meta` quand le backend a injecté `context.lyra` ; smoke `infra/scripts/smoke_bridge_ws_lyra.sh` durci (source `mmmorpg_ws`/`mmo_world`). |
| 2026-04-16 | **Monde v1 (seed)** : seed `mmo_server/world/seed_data/world_initial.json` enrichi (PNJ `npc:healer`, `npc:alchemist`, `npc:mayor`) + smoke LAN `infra/scripts/smoke_mmo_seed_npcs_lan.sh` (+ reset état persisté sur 245 pour recharger le seed). |
| 2026-04-16 | **Ops DevOps** : rotation `LBG_DEVOPS_APPROVAL_TOKEN` appliquée (orchestrator redémarré) et secrets poussés via `infra/scripts/push_secrets_vm.sh`. |
| 2026-04-16 | **Pilot UI** : `pilot_web/` enrichi (presets/chips pour les nouveaux PNJ + presets commit par PNJ) + déploiement front (110). |
| 2026-04-16 | **Smoke LAN pilot (nouveaux PNJ)** : ajout `infra/scripts/smoke_pilot_route_new_npcs_lan.sh` et validation `/v1/pilot/route` sur `npc:healer`, `npc:alchemist`, `npc:mayor` (trace_id + `lyra_meta.source`). |
| 2026-04-16 | **Revalidation LAN** : `smoke_vm_lan.sh`, `smoke_bridge_ws_lyra.sh`, `smoke_ws_ia_final_only_json.sh` re-lancés (OK). |
| 2026-04-16 | **Réconciliation IA→jeu (nouveau PNJ)** : `mmmorpg_server` seed enrichi (`npc:mayor`, `npc:healer`, `npc:alchemist`) + `smoke_mmmorpg_commit.sh` validé sur `npc:mayor` (commit 200 + snapshot `world_flags.quest_id=q:smoke`). |
| 2026-04-16 | **E2E commit via backend (nouveau PNJ)** : `smoke_commit_dialogue.sh` validé sur `npc:mayor` (`commit_result.accepted=true` + snapshot `world_flags.quest_id` OK). |
| 2026-04-16 | **E2E commit via backend (nouveaux PNJ)** : `smoke_commit_dialogue.sh` validé sur `npc:healer` et `npc:alchemist` (commit_result + snapshot OK). |
| 2026-04-16 | **Smoke LAN commit (nouveaux PNJ)** : ajout `infra/scripts/smoke_commit_dialogue_new_npcs_lan.sh` (enchaîne `npc:mayor|healer|alchemist`) et validation OK. |
| 2026-04-16 | **Validation complète (nouveaux PNJ)** : `infra/scripts/smoke_reset_seed_and_new_npcs_lan.sh` étendu (reset seed + smokes + commit E2E) et validation OK. |
| 2026-04-16 | **Pont WS→IA (nouveaux PNJ)** : ajout `infra/scripts/smoke_ws_ia_final_only_new_npcs_lan.sh` et validation `ws_ia_cli --final-only` sur `npc:mayor`, `npc:healer`, `npc:alchemist` (trace_id non vide). |
| 2026-04-16 | **One-shot nouveaux PNJ** : ajout `infra/scripts/smoke_all_new_npcs_lan.sh` (reset + HTTP + commit + WS→IA) et validation OK. |
| 2026-04-16 | **Smokes “quick/minimal”** : `smoke_lan_minimal.sh` validé (sans LLM) ; `smoke_lan_quick.sh` validé (timings). WS→IA (N=3) : min≈41.7s, p50≈50.4s, p95≈91.9s, max≈91.9s (LLM lent mais stable). |
| 2026-04-16 | **MMO v2+ (réputation locale)** : ajout `reputation_value` côté `mmo_server` (persisté/seed safe, borné) + exposition dans `lyra.meta.reputation.value` (mmo_server + snapshot interne WS) ; tests `mmo_server` + `mmmorpg_server` OK ; ajout `pytest.ini` monorepo (`--import-mode=importlib`) pour éviter collisions de tests. |
| 2026-04-16 | **MMO v2+ (réputation modifiable)** : ajout flag commit `reputation_delta` (backend whitelist + serveur WS autoritatif) ; snapshot interne expose la valeur persistée ; persistance mmmorpg state `schema_version=2` (backward compatible) ; tests backend+mmmorpg OK ; imports tests backend rendus explicites (`backend.main`). |
| 2026-04-16 | **Ops MMO (smoke réputation)** : ajout `infra/scripts/smoke_reputation_lan.sh` (sans LLM) pour commit `reputation_delta` via backend puis vérification snapshot interne. |
| 2026-04-16 | **Dialogue (réputation)** : `agents/dialogue_llm.build_system_prompt` inclut `lyra.meta.reputation.value` (ton PNJ légèrement adapté, sans afficher de score) ; tests agents OK. |
| 2026-04-16 | **Dialogue (cache & réputation)** : la clé de cache dialogue inclut la réputation (`lyra.meta.reputation.value`) pour éviter des réponses figées quand la réputation change ; tests agents OK. |
| 2026-04-16 | **Pilot (write gate)** : `POST /v1/pilot/reputation` protégé par token optionnel `LBG_PILOT_INTERNAL_TOKEN` ; UI `/pilot/` supporte `X-LBG-Service-Token` (champ local) ; smoke réputation lit aussi le token si défini ; tests backend OK. |
| 2026-04-16 | **Ops (smoke auth write)** : ajout `infra/scripts/smoke_pilot_reputation_auth_lan.sh` (401/200 selon token) pour valider le gate sur `POST /v1/pilot/reputation`. |
| 2026-04-16 | **Fallback monde cohérent (réputation)** : `mmo_server` expose `POST /internal/v1/npc/{npc_id}/reputation` (delta, token optionnel `LBG_MMO_INTERNAL_TOKEN`) et `POST /v1/pilot/reputation` écrit aussi vers `mmo_server` (best-effort) ; smokes `smoke_reputation_fallback_world_lan.sh` + option `LBG_SMOKE_WITH_REP_WORLD=1` dans `smoke_lan_quick.sh`. |
| 2026-04-16 | **Smokes réputation déterministes** : option `LBG_SMOKE_RESET_REP=1` (reset → 0) ajoutée aux smokes réputation + propagée dans `smoke_lan_quick.sh`. |
| 2026-04-16 | **Pilot UI** : ajout bouton “Reset rep (→0)” (delta auto) dans `pilot_web/`. |
| 2026-04-16 | **Ops scripts** : ajout `infra/scripts/fix_crlf.sh` (conversion CRLF→LF) + `bootstrap.md` mis à jour (correctif CRLF standardisé). |
| 2026-04-16 | **Secrets (template)** : `infra/secrets/lbg.env.example` réaligné sur la structure `infra/secrets/lbg.env` (placeholders, pas de secrets réels). |
| 2026-04-16 | **Fusion (doc)** : `docs/plan_fusion_lbg_ia.md` mis à jour (phase C : réputation + double-write monde + fiabilisation CRLF au déploiement). |
| 2026-04-16 | **Hygiène secrets** : scan patterns `gsk_/sk-/AIza` sur `LBG_IA_MMO/` (hors venv) sans match ; `infra/secrets/lbg.env` ignoré via `LBG_IA_MMO/.gitignore`. |
| 2026-04-16 | **LAN env** : `docs/fusion_env_lan.md` aligné (`LBG_MMO_INTERNAL_TOKEN`, `LBG_SSH_*`, `LBG_SKIP_FIX_CRLF` / `fix_crlf`). |
| 2026-04-16 | **Lyra (doc)** : `docs/lyra.md` — priorité snapshot `mmmorpg_ws`, fallback `mmo_world`, réputation + cohérence double-write. |
| 2026-04-16 | **Pilot (doc)** : `pilot_web/README.md` — contrôles réputation + token service (`LBG_PILOT_INTERNAL_TOKEN`) + endpoints associés. |
| 2026-04-16 | **Qualité tests** : `pytest` vert sur poste de dev “pollué” (imports orchestrator explicites, tests hermétiques vs env LAN/proxy, gate pilot réputation après validation 400, client httpx `trust_env=false`, boucle WS itère sur snapshot `clients`). |
| 2026-04-16 | **Plan / pause** : jalons “MMO v1 gameplay vs CI `pytest`” **reportés au lendemain** ; plan de route enrichi (section SSH — droits effectifs agent + poste de dev). |
| 2026-04-17 | **CI `pytest`** : ajout d’un entrypoint `infra/ci/test_pytest.sh` (venv `.venv-ci`) + workflow GitHub Actions `LBG_IA_MMO/.github/workflows/pytest.yml`. |
| 2026-04-17 | **MMO v1 gameplay (monde)** : ajout `POST /internal/v1/npc/{npc_id}/aid` (deltas jauges + réputation, bornés + auth optionnelle `LBG_MMO_INTERNAL_TOKEN`) + tests `mmo_server`. |
| 2026-04-17 | **Observabilité / ops** : métriques Prometheus opt-in (`/metrics` backend, orchestrator, HTTP interne `mmmorpg_server`) + variables dans unités systemd + tests CI ; **checklist déploiement** (`docs/runbook_validation_serveurs_lan.md` §2ter) ; **`pilot_web/`** : liens `/metrics`, Bearer local, fetch backend ; **`bootstrap.md`** : section systemd + secrets + lien runbook. |
| 2026-04-17 | **Doc + pause** : `architecture.md` (observabilité), `vision_projet.md` (point de situation monorepo) ; **pause nuit** — reprise prévue sur le jalon **MMO v1 gameplay** (voir *Prochaine étape* ci‑dessous). |
| 2026-04-18 | **MMO v1 gameplay — jalon #1** : boucle **observe → aid → observe** (jauges ↓ + réputation +Δ) formalisée ; exécution **hors LAN** via `pytest` (`mmo_server/tests/test_internal_aid.py`, `backend/tests/test_pilot_aid.py`) + intent `world_aid` (`orchestrator/tests/test_route.py`) ; recette LAN **`infra/scripts/smoke_mmo_v1_gameplay_jalon1_lan.sh`** (enchaîne `smoke_pilot_aid_lan.sh` + `smoke_commit_aid_lan.sh`) ; option **`LBG_SMOKE_WITH_GAMEPLAY_V1=1`** dans `smoke_lan_quick.sh`. |
| 2026-04-18 | **MMO v1 gameplay — jalon #2** : option WS **`move.world_commit`** (commit PNJ sans pont IA ; refus si `text`+`world_npc_id` IA sur le même message) ; snapshot **`GET …/lyra-snapshot`** sur HTTP interne **8773** ; tests **`mmmorpg_server/tests/test_ws_world_commit.py`** ; outil **`mmmorpg_server/tools/ws_world_commit_smoke.py`** ; smoke LAN **`infra/scripts/smoke_ws_move_commit_snapshot_lan.sh`** ; doc **`docs/mmmorpg_PROTOCOL.md`** ; option **`LBG_SMOKE_WITH_GAMEPLAY_V2=1`** dans `smoke_lan_quick.sh`. |
| 2026-04-18 | **LAN — déploiement + validation jalon #2** : **`bash infra/scripts/push_secrets_vm.sh`** (140 / 245 / 110) puis **`LBG_DEPLOY_ROLE=all bash infra/scripts/deploy_vm.sh`** ; contrôle **`healthz`** HTTP interne **245:8773** (token `LBG_MMMORPG_INTERNAL_HTTP_TOKEN`) avec **`protocol_features.ws_move_world_commit`** ; **`LBG_SMOKE_WITH_GAMEPLAY_V2=1 bash infra/scripts/smoke_lan_quick.sh`** **vert** (VM SSH + `smoke_lan_minimal` + smoke WS→snapshot réputation). |
| 2026-04-18 | **LAN — validation jalon #1** : **`LBG_SMOKE_WITH_GAMEPLAY_V1=1 bash infra/scripts/smoke_lan_quick.sh`** **vert** (`smoke_pilot_aid_lan.sh` + `smoke_commit_aid_lan.sh` sur core **140** ; `world_aid` + `commit_result.accepted` OK). |
| 2026-04-18 | **DevOps — capability `systemd_is_active`** : action `devops_action` **`kind: systemd_is_active`** + liste blanche **`LBG_DEVOPS_SYSTEMD_UNIT_ALLOWLIST`** (`systemctl is-active`, dry-run / approbation alignés sur `http_get`) ; tests **`agents/tests/test_devops_executor.py`** ; recette **`infra/scripts/smoke_devops_systemd_lan.sh`** ; option **`LBG_SMOKE_WITH_DEVOPS_SYSTEMD=1`** dans `smoke_lan_quick.sh` ; doc **`agents/README.md`** + **`lbg.env.example`**. |
| 2026-04-18 | **LAN — post feature DevOps** : **`LBG_DEPLOY_ROLE=core deploy_vm`** sur **140** ; puis **`LBG_DEVOPS_SYSTEMD_UNIT_ALLOWLIST`** dans **`infra/secrets/lbg.env`**, **`LBG_VM_HOST=192.168.0.140 bash infra/scripts/push_secrets_vm.sh`**, smoke **`bash infra/scripts/smoke_devops_systemd_lan.sh`** **vert** (dry-run `systemd_is_active` sur **`lbg-backend.service`**). |
| 2026-04-18 | **Orchestrateur / agents — « mains » ops (phase 1)** : action DevOps **`selfcheck`** (bundle HTTP healthz + `systemd_is_active`, URLs/unités **dérivées de l’env** et filtrées par allowlists ; défaut systemd **backend + orchestrateur** ; **`remediation_hints`** textuelles sans correctif exécuté) ; **`context.devops_selfcheck`** ; recette **`smoke_devops_selfcheck_lan.sh`** + option **`LBG_SMOKE_WITH_DEVOPS_SELFCHECK=1`** dans **`smoke_lan_quick.sh`** ; doc **`agents/README.md`**. |
| 2026-04-18 | **Agents multi-sites + chef de projet** : intent **`project_pm`** → **`agent.pm`** (`pm_stub` / HTTP **`LBG_AGENT_PM_URL`**, port **8055**) ; classifieur + **`context.pm_focus`** / **`project_pm`** ; **`lbg-agent-pm.service`** + **`deploy_vm`/`push_secrets`** ; pilot **`/v1/pilot/status`** + proxy **`/v1/pilot/agent-pm/healthz`** ; topologie documentée (**VM / dev**) dans **`agents/README.md`**. |
| 2026-04-18 | **LAN — selfcheck + PM (post-deploy)** : **`deploy_vm` core** + **`push_secrets`** sur **140** ; **`GET …/v1/pilot/status`** → **`agent_pm: ok`** ; smoke **`bash infra/scripts/smoke_devops_selfcheck_lan.sh`** **vert** (3 étapes, dry-run). |
| 2026-04-18 | **Boucle doc + garde-fous + pilot + secrets** : ligne **État courant** + **Étape actuelle** rafraîchies ; **`systemd_restart`** — quota fenêtre glissante + **fenêtre UTC** optionnelle (`LBG_DEVOPS_SYSTEMD_RESTART_*`) ; **phase 3** documentée (humain / Cursor exécute les hints) dans **`architecture.md`** ; **`pilot_web/`** — coque multi-vues (hash `#/chat`, `#/ops`, `#/pm`, `#/lyra`) inspirée de la lisibilité **LBG_IA** (orchestrateur Vue) ; page **Lyra (hors MMO)** = cadrage intégration **`context.lyra` / `output.lyra`** sans dépendre du WS **mmmorpg** ; **`push_secrets_vm.sh`** vers **140 + 245 + 110** (env partagé LAN). |
| 2026-04-18 | **Pilot PM — fin de sprint + pause** : extraction **`result.output.brief`** (jalons/tâches) ; encarts **Étape actuelle** / **File d’attente** ; URLs cliquables + pastilles **`docs/`** / **`infra/`** (copie presse-papiers) ; bouton **Exporter Markdown** ; **`LBG_DEPLOY_ROLE=all deploy_vm`** + **`smoke_lan_quick`** **vert** ; pilot **#/pm** validé en lecture sur le front LAN. **Reprise ultérieure** : voir *Étape actuelle* ci‑dessous. |
| 2026-04-24 | **Moteur ISO & IA Ville** : Layout en **losange (Diamond)** 2:1 aligné ; **Collisions bâtiments** (joueurs/PNJ) basées sur surface ; **Verticalité** (rampes/escaliers) + **filtrage caméra par étage** (0m vs 4m) ; **Patrouilles gardes** (9 gardes, rotation portes N/S, trajets croisés via centre-ville, départs différés) ; **Ollama branché** (`gemma4:e2b` sur 110 via LAN) ; **`deploy_vm` / `push_secrets`** (corrections guillemets/typos). |
| 2026-04-24 | **Optimisation Navigation & Dialogue** : Correction inversion des axes (Z/Q/S/D) ; **Sélection PNJ au clic** sur canevas ; **Assets Tavern/Forge** haute résolution ; Passage sur **Groq (Llama 3.1)** pour l'IA dialogue; retour sur Ollama avec gemma4:e2b; Correction de l'affichage des noms PNJ dans le chat. |
| 2026-04-25 | **Village Visuel & Zoom** : Intégration de la carte du monde (`planet_map.png`), alignement précis des bâtiments et PNJ sur le décor. Ajout d'un système de zoom/dézoom à la molette. |
| 2026-04-25 | **Expansion Continentale** : Génération d'une carte 4K stylisée (`planet_map.png`) avec routes, forêts et rivières. Déploiement à l'échelle 102km x 51km. Système de zoom orbitale (0.001) et HUD en mètres. |
| 2026-04-25 | Basculement sur **Gemma4:e2b** (Ollama VM 110) avec timeout 240s. Correction des **patrouilles des gardes** (WebSocket) : navigation réelle vers les Portes et la Place d'Armes. Peuplement de l'**Auberge de la Pomme Rouge** (Barnabé, Élise, etc.). |
| 2026-04-26 | **Génération de Zones Locales** : Intégration de `area_gen.py` (villes, villages, zones de ruines, donjons extérieurs) pour le peuplement futur des points d'intérêt sur le continent. |
| 2026-04-27 | **Urbanisme & Physique v1.1** : Correction de l'échelle du village (16px/m), bouclage du monde (World Wrap à ±51km) et interpolation consciente du bouclage côté client. Stabilisation du mouvement des personnages (bobbing). |
| 2026-04-27 | **Unification Architecture Front (Port 8080)** : Fusion de Lyra (racine) et du client MMO (servi sous la **route** `/mmo/`) sous Nginx sur la VM 110. Suppression définitive du service 8081. Mise à jour des scripts de déploiement automatique. |
| 2026-04-27 | **Correctif Chemins Relatifs** : Passage des assets en relatif (`assets/...`) dans `renderer.js` pour garantir le chargement depuis le sous-dossier `/mmo/` sans erreur. (Build déployé dans `pilot_web/mmo/` : les assets réels vivent dans `pilot_web/mmo/assets/`.) |
| 2026-04-27 | **Sync Explorateur Local** : Mise à jour de `deploy_web_client.sh` pour synchroniser le build MMO vers `LBG_IA_MMO/pilot_web/mmo/` (visibilité locale assurée). |
| 2026-04-27 | **Collisions Solides v1.2** : Passage des bâtiments en mode `hollow=False` (pleins) sur le serveur pour interdire la traversée des murs. Ajustement de la marge de précision à 0.5. Déploiement VM 245. |
| 2026-04-27 | **Régénération PNG Village v1.4** : Passage au buffer XXL (7x5) dans `area_gen.py` pour garantir l'absence totale de chevauchements de bâtiments. Arbres repoussés davantage des toits. PNG déployé. |
| 2026-04-28 | **Alignement Bâtiments v1.5** : Synchronisation des coordonnées (x, z) et dimensions (w, h) des bâtiments dans `world_initial.json` pour correspondre parfaitement aux rectangles rouges générés dans `bourg_palette_map.png`. Correction du décalage d'axes (y/z) et application de tailles variées (ex: Auberge plus grande que la Mairie). |
| 2026-04-28 | **Pilot web — Lyra (standalone) visuel** : page `#/lyra` branchée sur `POST /v1/pilot/route` (`context.lyra` → `result.output.lyra`) sans dépendre du WS ; affichage **Énergie dérivée** (moyenne faim/soif/fatigue) + **Confiance** canonique (0–100) + **Stress** (vue `100 - confiance`) ; déploiement **front 110** (`deploy_vm.sh` rôle `front`). Doc fusion mise à jour : `fusion_spec_lyra.md` (§6) + `plan_fusion_lbg_ia.md` (§3.2). |
| 2026-04-29 | **Sync GitHub corrigée** : résolution du blocage `GH001` (fichier >100MB dans l’historique : runtime Godot `.exe`) ; nettoyage/rebase de l’historique local, ajout des garde-fous `.gitignore` (runtime Godot + `node_modules`), push `main` validé puis push `chore/sync-cleanup` validé. |
| 2026-04-29 | **Cadrage dialogue orchestré (backlog)** : besoin formalisé pour orienter les requêtes de dialogue vers plusieurs LLM (locaux + distants) avec garde-fous coût ; ajout du chantier “profils de style”, “registre PNJ contextualisé” et “base de suivi dialogue/coût/latence”. |
| 2026-04-29 | **Client MMO — stabilisation après régression** : restauration d’un bundle “stable” servi sous `/mmo/` (Nginx VM 110) après un build qui cassait le rendu ; **le build Vite peut écraser** `pilot_web/mmo/` et provoquer un mismatch *HTML → assets*. Correctif côté WS : `Entity.to_snapshot()` inclut désormais `stats` (et `role/ry/scale`) afin que le HUD (barres HP/MP/Énergie) se mette à jour sur chaque `world_tick`. Déploiement : redémarrage `lbg-mmmorpg-ws` sur VM 245. |

---

## Prochaine étape concrète

**Règle** : une **seule** phrase actionnable à la fois ; quand elle est **faite**, la remplacer par la suivante et, si utile, ajouter une ligne dans **État courant** ci‑dessus.

- [x] **Jalon #5 : Physique & Collisions (Priorité 3)** : Bloquer les murs du village (`hollow=False`), ajuster les marges et régénérer le PNG sans chevauchements (v1.4).
- [/] **Jalon #6 : Interactions & Dialogue (Priorité 2/3)** : Bulles riches + ciblage PNJ **faits** ; **inventaire session v1** (`stats.inventory`, HUD Sac) **fait** ; suite : interactions objets / commits inventaire, etc.

**Étape actuelle** : **(A)** *Étoile du nord — rang 1* : renforcer l’**assistant poste / infra** (`desktop_control`, workers, audit, parcours du type Notepad / URL / mail — voir `desktop_hybride.md`). **(B)** *Jalon #6* : après inventaire session v1 — **commits inventaire** (HTTP interne + backend) et/ou **interactions objets** (stub), sans relâcher ADR 0004.

**File d’attente (intention produit)** : **Développement de l'univers MMO** — implémentation des niveaux de détails de simulation PNJ (LOD), Ticks sociaux, événements dynamiques (voir `plan_mmorpg.md`).

**Parking validé (à reprendre)** :
- **Dialogue multi‑LLM** : **`auto` livré** (ordre + budget soft) ; prolongations possibles : budgets par `actor_id`, persistence disque du compteur, circuit‑breaker latence.
- **Profils conversationnels** : base `guardrails` + profils côté assistant (`chaleureux`, `professionnel`, `pedagogue`, `creatif`, `mini-moi`, `hal`, `test`) et variante MMO PNJ (`pnj_name` + style).
- **Registre PNJ exhaustif** : liste des PNJ avec contexte minimal (rôle, zone, faction, ton, objectifs, contraintes).
- **Base de suivi** : **journal JSONL + `meta.trace` enrichi** ; prolongations : agrégation Prometheus, export vers BI, corrélation coût réel vs estimé.

**Historique** : CI `pytest` fait (entrée 2026-04-17 ci‑dessus).

**Historique récent (déjà livré, rappel)** : smokes LAN harmonisés / `smoke_lan_quick.sh` / auth `LBG_MMO_INTERNAL_TOKEN` / CRLF + `deploy_vm` / alignement `lbg.env.example` / doc SSH `LBG_SSH_*` / docs fusion+Lyra+`plan_mmorpg` / `pytest` vert — détail dans les lignes **État courant** du **2026-04-16**.

### SSH — droits effectifs (poste de dev **et** agent Cursor)

- **Côté VM (inchangé)** : compte **`lbg`** sur les hôtes LAN, clé publique dans `authorized_keys`, **`sudo` NOPASSWD** sur une **liste blanche** d’actions utiles au déploiement — voir `docs/ops_vm_user.md` et `../../bootstrap.md`.
- **Côté poste de travail (humain ou agent)** : **aucun “nouveau droit SSH” magique** pour l’agent IA — il exécute les mêmes commandes qu’un terminal local, avec les **mêmes prérequis** :
  - **`LBG_SSH_IDENTITY`** : chemin vers la **clé privée** lisible par le process (ex. sous WSL : `"$HOME/.ssh/id_ed25519"` — éviter les chemins Windows `\\wsl.localhost\...` pour la valeur exportée).
  - **`LBG_SSH_KNOWN_HOSTS_FILE`** (optionnel mais recommandé si `~/.ssh` n’est pas écrivable) : fichier `known_hosts` **dédié** ; utilisé par `infra/scripts/smoke_vm_lan.sh` (évite les erreurs “cannot write known_hosts”).
  - **`LBG_VM_USER` / `LBG_VM_HOST`** : comme documenté pour `deploy_vm.sh` / smokes ; sans réseau vers le LAN ou sans clé, **`ssh` échoue** comme pour un humain.
- **Persistance des `export`** : un reboot ou une nouvelle session shell **ne** conserve **pas** les variables — les remettre dans `~/.bashrc` / `~/.profile` si tu veux le comportement “direct au login”.
- **Agent Cursor en bac à sable** : si l’environnement d’exécution **n’a pas** accès à ta clé ou au LAN, les scripts SSH/smokes **échouent** ; dans ce cas, lancer les mêmes commandes depuis **ton** terminal WSL avec `LBG_SSH_*` exportés.
- **Quand l’accès LAN + clé est OK** : l’agent peut exécuter directement les scripts d’ops (ex. `LBG_DEPLOY_ROLE=all bash infra/scripts/deploy_vm.sh`, `bash infra/scripts/push_secrets_vm.sh`) et faire une validation “post-deploy” via `curl` (endpoints `/healthz`, `/v1/pilot/*`) — comme depuis un terminal humain.

---

## Documents liés

- `lexique.md` — **termes, acronymes, définitions** (dont **ADR**) pour transmission du projet
- `architecture.md` — architecture et règles réseau
- `carte_plan_global.md` — alignement plan large (`.cursor/rules`) ↔ modules réels et backlog
- `runbook_validation_serveurs_lan.md` — validation rapide LAN (santé, smokes, **métriques §2bis–2ter**)
- `ops_pont_interne_auth_rl.md` — ops : token service + rate-limit du pont interne `mmmorpg_server` → backend
- `plan_fusion_lbg_ia.md` — **fusion LBG_IA + LBG_IA_MMO + mmmorpg** (phases, correspondances, matrice tronc, pont jeu ↔ IA)
- `fusion_etat_des_lieux_v0.md` — **état des lieux fusion v0** (inventaire HTTP / WS, pont env)
- `fusion_spec_lyra.md` / `fusion_spec_agents.md` / `fusion_spec_monde.md` — **specs fusion** phase B
- `fusion_pont_jeu_ia.md` — **pont jeu ↔ IA** (brouillon)
- `mmmorpg_PROTOCOL.md` — protocole WebSocket (copie portage)
- `../mmmorpg_server/README.md` — serveur WS porté dans le monorepo
- `docs/adr/0001-tronc-monorepo.md` — **ADR** : tronc unique monorepo, dépôts sources non modifiés
- `docs/adr/0002-mmo-autorite-pont.md` — **ADR** : autorité **`mmmorpg`** vs **`mmo_server`**, pont jeu ↔ IA
- `fusion_env_lan.md` — **topologie LAN** : IPs **140 / 245 / 110**, table **`LBG_*`**, déploiement, option **frontend sur 110**
- `vision_projet.md` — vision orchestrateur / agents / MMO
- `lyra.md` — périmètre Lyra
- `plan_mmorpg.md` — feuille de route technique MMO
- `../../bootstrap.md` — installation et déploiement
