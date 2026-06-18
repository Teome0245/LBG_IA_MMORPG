# Assistant Core — plan d'action

Ce document devient le plan de travail du recentrage **IA conversationnelle incarnée**, capable d'agir sur le poste, l'infra et, ensuite, le MMO.

Il s'appuie sur la vision de la Boite a idees : d'abord un assistant local concret, ensuite une presence dans le MMO, enfin une capacite a proposer et preparer des evolutions du projet sous controle humain.

## But

Construire dans `LBG_IA_MMO/` un noyau **Assistant Core** qui sait :

- dialoguer avec l'utilisateur dans une interface simple ;
- introspecter ses agents, capabilities, contraintes et etats disponibles ;
- transformer une demande naturelle en action structuree ;
- router l'action vers un agent local ou distant ;
- demander confirmation pour les actions sensibles ;
- executer, auditer, resumer et proposer une suite utile ;
- rester separe du mode `mmo_persona`, tout en permettant un pont explicite plus tard.

Le noyau cible doit remplacer les reponses passives du type "je ne peux rien faire" par un comportement operationnel : **dire ce qui est possible, proposer une action validee, l'executer si autorise, puis journaliser le resultat**.

## Decisions de cadrage

### Source de verite

- Le tronc cible reste **ce monorepo** : `LBG_IA_MMO/`.
- `~/projects/LBG_IA/` reste une **source en lecture** : on y reprend les bons patterns, pas une seconde stack a maintenir.
- Les modules existants `desktop_control`, `agent.desktop`, workers Windows/Linux, `agent.devops`, `agent.pm`, `Lyra` et `mmmorpg_server` sont des briques a consolider, pas a remplacer brutalement.

### Routage LLM (reseau + config seulement)

- **Decision** : aligner **URLs**, **cles API** et **modeles** entre LBG_IA (providers historiques) et le dialogue monorepo via l’environnement, **sans** exiger un port du `RouterIA` / des modules `providers/` dans `LBG_IA_MMO/`.
- **Exigence produit** : un **routeur LLM unique** dans le monorepo **n’est pas** au catalogue ; la convergence par **config** (`lbg.env`) suffit.
- **Operational** : pour `lbg_agents` (`dialogue_llm.py`), renseigner `LBG_DIALOGUE_FAST_*` et `LBG_DIALOGUE_REMOTE_*` (plus `LBG_DIALOGUE_AUTO_ORDER`, failover, budget) avec les **memes** endpoints OpenAI-compatibles (`…/v1`) et jetons que ceux utilises par la stack LBG_IA pour Groq, OpenRouter, etc. Detail des variables : `infra/secrets/lbg.env.example`, `agents/README.md`. Un catalogue ou routeur partage dans le monorepo reste **hors scope** tant qu’aucune nouvelle exigence ne le demande.

### Modes separes

- `local_assistant` : actions poste, fichiers, web, mail, infra du proprietaire.
- `mmo_persona` : dialogue et comportement dans le monde simule.
- Aucun transfert automatique du contexte prive vers le MMO.
- Un pont volontaire pourra transmettre des resumes bornes, par exemple `session_summary`, jamais des donnees brutes de mail ou disque.

Reference : `docs/adr/0004-assistant-local-vs-persona-mmo.md`.

### Capabilities initiales

Capabilities a stabiliser ou declarer explicitement :

- `assistant.chat` : discussion, clarification, synthese.
- `assistant.introspect` : liste agents/capabilities/contraintes disponibles.
- `desktop.open_app` : ouvrir une application allowlistee.
- `desktop.type_text` / `desktop.notepad_append` : dictee ou ecriture bornee.
- `desktop.web_search` : recherche web ouverte via moteur allowliste.
- `desktop.mail_preview` : lecture IMAP INBOX en apercu, read-only.
- `desktop.observe` : capture ou observation ecran avec opt-in.
- `infra.selfcheck` : diagnostic systeme borne.
- `infra.service_status` : etat systemd allowliste.
- `project.pm` : planification, backlog, suivi de jalons.
- `mmo.session_summary` : resume volontaire d'une session MMO vers l'assistant local.

Chaque capability doit avoir : nom stable, description, input schema, output schema, preconditions, effets, erreurs possibles et contraintes d'execution.

### Protocole agent

Surface cible :

- `GET /capabilities` pour les agents generiques ou distants ;
- `POST /execute` comme profil generique herite de `LBG_IA` ;
- `POST /invoke` comme profil deja utilise par les agents du monorepo ;
- un adaptateur unique, si necessaire, pour convertir `execute` vers `invoke`.

La convergence suit `docs/fusion_spec_agents.md` : pas de big bang, une seule couche de traduction.

### Contraintes executables

Les contraintes ne doivent pas rester des intentions de prompt. Elles doivent etre appliquees par le code :

- dry-run par defaut sur actions poste/infra ;
- allowlists obligatoires pour URLs, fichiers, apps, unites systemd ;
- approval token ou confirmation humaine pour execution reelle ;
- refus explicite des actions hors scope ;
- audit JSONL pour toute action sensible ;
- pas de log de secrets, tokens, mots de passe, contenu mail complet ;
- pas d'auto-modification du repo canon sans revue humaine.

### Schemas JSON

Contrats a versionner dans le monorepo :

- `AssistantRequest` : `actor_id`, `text`, `mode`, `context`, `trace_id`.
- `CapabilitySpec` enrichi : `name`, `agent`, `description`, `input_schema`, `output_schema`, `constraints`, `effects`.
- `ActionProposal` : proposition structuree avant execution.
- `ActionResult` : resultat normalise apres agent.
- `AssistantEvent` : journal conversation/action pour audit et UX.

Les schemas peuvent etre Pydantic au debut, avec export JSON Schema lorsque les contrats deviennent consommes par plusieurs composants.

### Logs

Champs minimaux :

- `timestamp`
- `level`
- `trace_id` ou `request_id`
- `mode`
- `agent`
- `capability`
- `action_kind`
- `outcome` : `success`, `error`, `rejected`, `dry_run`, `approval_required`
- `latency_ms`
- `error_type`
- `error_message` sans secret

## Architecture cible

Flux nominal :

```text
Pilot / Chat
  -> Backend
  -> Assistant Core
  -> Introspection + policy
  -> Router capability
  -> Agent local/distant
  -> Audit + resultat
  -> Resume utilisateur + suggestion suivante
```

Composants :

- **Interface** : reutiliser `pilot_web` au depart, puis envisager un chat plus riche inspire de `LBG_IA`.
- **Assistant Core** : couche d'orchestration conversationnelle au-dessus du routeur existant.
- **Registry declaratif** : source unique des agents, capabilities, contraintes et schemas.
- **Policy engine** : validation deterministic avant toute action.
- **Agent adapters** : pont `invoke` / `execute` pour reprendre les agents utiles de `LBG_IA`.
- **Memory light** : preference utilisateur et resume de session, sans store semantique lourd au premier jalon.
- **Lyra** : etat d'incarnation et style, mais sans melanger les secrets du mode local avec le MMO.

## Plan de realisation

### Jalon 0 — Canoniser le cap

Statut : en cours.

Livrables :

- ce document ;
- liens depuis `README.md` et `plan_de_route.md` ;
- prochaine etape unique inscrite dans le plan de route.

Definition de fini :

- l'equipe sait ou lire le plan Assistant Core ;
- le rang 1 "assistant poste / infra" devient le chantier actif ;
- les sources `LBG_IA` a reprendre sont identifiees sans les modifier.

### Jalon 1 — Registry declaratif enrichi

Statut : demarre. Premier increment livre : `CapabilitySpec` expose maintenant `mode`, `protocol`, `risk_level`, `action_context_key`, `input_schema`, `output_schema`, `preconditions`, `effects`, `errors`, `constraints` et `tags`; les capabilities existantes sont renseignees dans le registry central.

Objectif : transformer la liste plate de capabilities en catalogue actionnable.

Livrables :

- [x] `CapabilitySpec` enrichi ou nouveau schema equivalent ;
- [x] champs `constraints`, `input_schema`, `output_schema`, `effects`, `risk_level` ;
- [x] endpoint d'introspection lisible par l'UI, via `GET /v1/capabilities` ;
- [x] tests de validation des capabilities ;
- [ ] exploitation UI plus riche dans le Pilot ;
- [ ] policy engine consommant directement ces metadonnees.

References a reprendre :

- `LBG_IA/orchestrateur/backend/src/services/agent_catalog.py`
- `LBG_IA/orchestrateur/backend/src/services/agent_introspection.py`
- `LBG_IA_MMO/orchestrator/shared_registry.py`
- `LBG_IA_MMO/orchestrator/capabilities/spec.py`

### Jalon 2 — Policy engine local assistant

Statut : premier increment livre. Le routeur evalue une policy deterministe avant dispatch agent et renvoie `output.policy` avec `decision`, `allowed`, `reason`, `risk_level`, `action_kind` et contraintes appliquees. Les decisions initiales sont `safe_read`, `dry_run`, `approval_required`, `forbidden` et `approved_action`.

Objectif : refuser, demander confirmation ou autoriser avant routage.

Livrables :

- [x] politique deterministic pour `desktop_*`, `mail_*`, `infra_*` ;
- [x] classification de risque : `safe_read`, `dry_run`, `approval_required`, `forbidden`, `approved_action` ;
- [x] blocage avant dispatch quand une action sensible n'a ni dry-run ni approbation ;
- [x] tests de refus, dry-run, approval manquant et action autorisee ;
- [ ] UI Pilot affichant clairement la decision de policy ;
- [ ] policies d'allowlist plus fines au niveau orchestrateur si on veut pre-valider avant worker.

References a reprendre :

- `LBG_IA/orchestrateur/backend/src/services/routing_policy.py`
- `LBG_IA/orchestrateur/backend/src/services/policy_engine.py`
- `LBG_IA_MMO/agents/src/lbg_agents/devops_executor.py`
- `LBG_IA_MMO/agents/src/lbg_agents/desktop_executor.py`

### Jalon 3 — Conversation -> proposition d'action

Statut : premier increment livre. L'orchestrateur expose `POST /v1/action-proposal`, qui transforme certains textes naturels en `ActionProposal` editables sans executer l'action. Parcours couverts : Notepad append, recherche web, apercu mail IMAP filtre, selfcheck infra, et refus propre si aucune action sure n'est reconnue.

Objectif : une demande naturelle produit une proposition structuree, pas une execution directe.

Exemples :

- "ouvre notepad et ecris ..." -> `desktop.notepad_append`
- "cherche le site de machin" -> `desktop.web_search`
- "regarde si j'ai un mail de Intel" -> `desktop.mail_preview`
- "verifie l'etat du backend" -> `infra.selfcheck`

Livrables :

- [x] objet `ActionProposal` ;
- [x] endpoint `POST /v1/action-proposal` ;
- [x] propositions deterministes pour `notepad_append`, `search_web_open`, `mail_imap_preview`, `devops selfcheck` ;
- [x] tests de sanitisation / extraction de base ;
- [x] rendu UI pour relire/editer la proposition (`pilot_web` `#/assistant`) ;
- [x] bouton "executer en dry-run" puis "executer reel" si autorise ;
- [ ] integration optionnelle d'un planificateur LLM borne derriere la meme enveloppe.

### Jalon 4 — UX Assistant local

Statut : premier increment livre. Le Pilot expose `#/assistant` avec saisie texte/context, presets, appel proxy `POST /v1/pilot/action-proposal`, edition JSON de la proposition, application vers le context, execution dry-run ou reelle via `POST /v1/pilot/route`, et affichage du resultat/policy.

Objectif : rendre l'assistant utilisable au quotidien depuis le Pilot.

Livrables :

- [x] une vue `#/assistant` ou evolution de `#/desktop` ;
- [x] historique court de conversation ;
- [ ] panneau capabilities disponibles ;
- [x] affichage clair : proposition, risque, statut, resultat, trace_id ;
- [x] suggestion proactive post-action : "je peux ajouter un smoke", "je peux memoriser cette preference", etc.

### Jalon 5 — Memoire legere et curiosite controlee

Statut : **increment principal livre** dans `#/assistant` : memoire locale navigateur (historique, preferences, suggestions), plus **resume de session volontaire** genere en JSON (notes + historique, copie locale, pas d'envoi serveur implicite).

Objectif : donner une continuite sans creer une surface de fuite.

Livrables :

- [x] preferences locales explicites : editeur prefere, moteurs, dossiers autorises, style de reponse ;
- [x] resume de session volontaire ;
- [x] suggestions proactives limitees a des actions non destructives ;
- [x] journal consultable des initiatives proposees/refusees/acceptees.

Non objectif de ce jalon : RAG global sur tout le disque.

### Jalon 6 — Pont doux vers le MMO

Statut : **premier increment livre** — import volontaire avec trace `mmo_bridge` ; proposition determinee **OpenGame** (`prototype_game`, dry-run) lorsque le texte evoque forge/prototype et que `session_summary` + `mmo_bridge.source=mmo_session_summary` sont presents ; **`mmo_trace`** dans l'API proposition ; tests garantissant que la proposition MMO n'embarque pas de `desktop_action`.

Objectif : brancher le monde simule sans melanger les contextes.

Livrables :

- [x] import volontaire d'un `session_summary` MMO vers `local_assistant` (UI + stockage partage avec `#/desktop`) ;
- [x] proposition d'actions de developpement du MMO sous forme de plan/patch (forge sandbox), jamais auto-merge ;
- [x] trace explicite quand une idee vient du MMO (`mmo_trace`, `source: mmo_session_bridge`) ;
- [x] tests de non-fuite : proposition MMO pont sans `desktop_action` ; isolation persona formalisee dans l'ADR (hors scope : audit runtime dialogue).

### Jalon 7 — Moteur de jobs autonome ("type Cowork", sous garde-fous)

Statut : **premier increment livre**. L'orchestrateur sait maintenant transformer un **objectif en langage naturel** en un **plan multi-etapes**, l'executer **en tache de fond** et **se corriger** (retry borne) — l'ecart cle avec un agent autonome facon *Claude Cowork*, mais sans jamais contourner la policy d'actions.

Objectif : remplacer le chainage **manuel** (proposition → route → reinjection) par une boucle **objectif → plan → execution → observation → correction**, pilotable et reprenable.

Composants livres :

- **Planner** (`orchestrator/services/planner.py`) : decoupe l'objectif en clauses puis reutilise `propose_action_from_text` (meme brique que `POST /v1/action-proposal`) pour mapper chaque clause sur une **capability du registry**. Planner **LLM optionnel** opt-in (`LBG_JOBS_PLANNER_LLM`) qui produit un plan JSON revalide contre une allowlist ; repli deterministe systematique. Allowlist de planification : `npc_dialogue`, `project_pm`, `devops_probe`, `desktop_control`, `prototype_game`, `unknown`.
- **Moteur de jobs** (`orchestrator/services/jobs.py`) : modele `Job` / `JobStep` avec machine a etats (`queued → planning → running → waiting_approval → done/failed/cancelled`), persistance best-effort JSON (`LBG_JOBS_STATE_PATH`), timeline d'evenements (`orchestrator.jobs.*`), boucle **observe→agit→corrige** (`advance_job`, pur et testable) et **runner daemon** (`ensure_started`, gate `LBG_JOBS_RUNNER_ENABLED`, **off par defaut** comme le Brain).
- **API** (`orchestrator/router/routes/jobs.py`) : `POST /v1/jobs`, `GET /v1/jobs`, `GET /v1/jobs/{id}`, `POST /v1/jobs/{id}/approve`, `.../cancel`, `.../advance`.

Garde-fous (ce qui distingue de Cowork "grand public") :

- chaque etape passe par `evaluate_action_policy` **avant** dispatch ;
- perimetre restreint du premier increment : actions a effet de bord **forcees en dry-run** ;
- autonomie **semi-auto par token** : un job peut etre **pre-autorise** (`approval_token` valide vs `LBG_JOBS_APPROVAL_TOKEN`) pour enchainer une action reelle ; sinon l'etape a risque met le job en `waiting_approval` (reprise via `/approve`), jamais d'action en aveugle ;
- aucune auto-modification du tronc (ADR 0003 / 0004 respectes : forge OpenGame en dry-run, pas d'auto-merge).

Livrables :

- [x] modele `Job` / `JobStep` persistant + machine a etats ;
- [x] planner deterministe (objectif → etapes mappees registry) + planner LLM optionnel borne ;
- [x] runner daemon de fond + avancement pur `advance_job` ;
- [x] boucle d'auto-correction (retry borne `LBG_JOBS_STEP_MAX_ATTEMPTS`) ;
- [x] gate token semi-auto + pause `waiting_approval` / reprise `/approve` ;
- [x] endpoints `/v1/jobs*` ;
- [x] tests `orchestrator/tests/test_jobs.py` (plan, execution, auto-correction, pause/approve, annulation) ;
- [x] vue Pilot `#/jobs` (creation, liste, timeline live, approbation/annulation/avance en un clic) — proxies `/v1/pilot/jobs*` ;
- [x] elargissement du perimetre aux actions a effet de bord reelles sous token, **capability par capability** (`LBG_JOBS_REAL_CAPABILITIES`) ;
- [x] persistance **Redis** optionnelle (`LBG_JOBS_REDIS_URL`), prioritaire sur le JSON, fallback fichier/memoire ;
- [x] indexation Redis par job (cle par job `{prefix}:job:{id}` + set d'index `{prefix}:index`) au lieu d'un snapshot unique, pour le multivers a grande echelle (`LBG_JOBS_REDIS_LAYOUT=index`, defaut ; `LBG_JOBS_REDIS_PREFIX`).

## Tests

Tests minimaux par jalon :

- validation schema capabilities ;
- routage intention vers capability ;
- refus action sensible sans confirmation ;
- dry-run action desktop ;
- action devops read-only ;
- introspection "quels agents/capabilities as-tu ?";
- logs avec `trace_id` et sans secret ;
- separation `local_assistant` / `mmo_persona`.

## Documentation a maintenir

Chaque jalon notable doit mettre a jour :

- `docs/plan_de_route.md` : historique + prochaine etape ;
- `docs/assistant_core_plan.md` : statut du jalon ;
- `docs/desktop_hybride.md` si une action poste change ;
- `docs/fusion_spec_agents.md` si le protocole agent change ;
- `infra/secrets/lbg.env.example` si une variable est ajoutee ou change de sens ;
- `agents/README.md` si un agent/capability change.

## Premier chantier concret

Demarrer par le **Jalon 1 — Registry declaratif enrichi**.

Pourquoi :

- c'est le socle qui rend l'assistant introspectable ;
- cela evite les "capabilities fantomes" ;
- cela permet ensuite de brancher policies, UI et propositions d'action sans refaire le modele ;
- c'est le point de convergence naturel entre `LBG_IA` et `LBG_IA_MMO`.

Premiere tache technique proposee :

1. lire `orchestrator/capabilities/spec.py`, `shared_registry.py` et `registry/in_memory.py` ;
2. definir le schema cible minimal compatible avec l'existant ;
3. enrichir les capabilities `desktop_control`, `devops_probe`, `project_pm`, `npc_dialogue` ;
4. exposer l'introspection enrichie ;
5. ajouter les tests.
