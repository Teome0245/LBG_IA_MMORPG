# Greffon sur le monorepo LBG_IA_MMO

Ce document décrit **comment brancher** le paquet une fois le comportement validé. Aucune étape n’est obligatoire tant que tu n’as pas choisi un point d’ancrage.

## 1. Déclarer la dépendance

Depuis `LBG_IA_MMO/orchestrator/` (ou `backend/`, `agents/`, selon le choix), ajouter une dépendance **locale** ou **workspace** vers le répertoire du paquet :

```toml
# exemple pyproject.toml (chemins relatifs à ajuster)
dependencies = [
  "hybrid-proactive-agent @ file:///${PROJECT_ROOT}/LBG_IA_MMO/hybrid_proactive_agent",
]
```

En pratique tu utiliseras souvent **`pip install -e ../hybrid_proactive_agent`** dans le même venv que l’orchestrateur pendant le développement.

## 2. Points d’ancrage possibles

| Lieu | Moment d’appel | Usage |
|------|----------------|--------|
| **Orchestrateur** | Après classification d’intention, avant dispatch | Enrichir `context` ou `output` avec `integration_hints` |
| **Backend Pilot** | Lors d’un tour de conversation assistant | Proposer une question proactive dans la réponse JSON |
| **Agent dialogue** | Entre intent utilisateur et génération LLM | Injecter `long_term_recall` + hints dans le prompt |
| **Client MMO** | Timer + dernier message WS | UI : pastille « relance » locale (`HybridProactiveEngineWeb` TS) |

## 3. Séquence type (orchestrateur)

1. Construire un **`context`** aligné sur ton contrat Pilot (intent, objectif, contraintes, flags flou / missing).
2. **`engine.observe_user_turn(texte_utilisateur, context)`**.
3. **`action = engine.decide(context)`** si tu veux une initiative dans **ce** tour ; sinon **`tick_silence`** sur timer en parallèle.
4. Fusionner **`integration_hints(engine.state, world_slice)`** dans **`output`** ou **`orchestrator_route_meta`** (nom de champs à figer dans une mini-ADR si besoin).
5. Appeler **`cooldown_decay()`** après avoir envoyé une proactive pour éviter les rafales.

## 4. Garde-fous produit

- **Quota** : ne pas appeler `decide` à chaque requête HTTP sans plafond ; utiliser `cooldown_decay` + compteur par session.
- **Opt-in** : exposer un flag utilisateur « suggestions automatiques ».
- **Traçabilité** : journaliser `ProactiveAction.model_dump()` avec `trace_id`.

## 5. Cohérence avec le Brain existant

Le service **`brain`** de l’orchestrateur a déjà des jauges et un tick périodique : le moteur hybride peut **coexister** comme couche « dialogue / intention utilisateur » ou être **fusionné** plus tard (ex. tension hybride → entrée de la jauge `curiosity`). Ce greffon ne impose pas de fusion immédiate.

---

## 6. Matérialisation concrète : où ça vit, de quoi ça a besoin, comment ça « parle »

### 6.1 Où le greffon s’installe-t-il ?

Il n’y a **pas de service séparé obligatoire**. Le paquet est une **bibliothèque Python** (`hybrid_proactive_agent`) :

- **Sur le disque** : dossier `LBG_IA_MMO/hybrid_proactive_agent/` (déjà dans le monorepo).
- **Dans l’environnement d’exécution** : le greffon consiste à **`pip install -e ../hybrid_proactive_agent`** (ou équivalent) dans le **même venv** que le composant qui l’appelle (souvent **`orchestrator/`**, parfois **`backend/`** si tu veux enrichir une réponse Pilot sans passer par FastAPI orchestrateur).
- **Dans le code** : quelques lignes à des **points d’ancrage** (ex. après le routage dans `POST /v1/route`, ou dans le backend qui proxy vers l’orchestrateur).

Autrement dit : le greffon **s’incarne** comme **dépendance + appels** dans un process existant, pas comme un nouveau conteneur à déployer (sauf si tu choisis volontairement un worker dédié plus tard).

### 6.2 De quoi le moteur a-t-il besoin pour « exister » et fonctionner ?

**Minimum technique :**

| Besoin | Rôle |
|--------|------|
| **Python ≥ 3.10** + **Pydantic** | Déjà aligné avec le reste du monorepo. |
| **Une instance de moteur par conversation** (ou par `actor_id` / session) | L’état interne (`tension`, `objectifs`, mémoire courte) n’est pas global au serveur entier : tu dois **stocker** ou **recréer** l’état si tu veux de la continuité après redémarrage (voir ci‑dessous). |
| **Un `context` structuré** | Même grain que le Pilot : idéalement `intent`, `objectif`, `contraintes`, flags `missing_info` / `objectif_flou` / `incoherent`, et plus tard des clés monde (`npc_id`, `session_id`, …). |
| **Appels orchestrés** | `observe_user_turn` quand il y a un message utilisateur ; **`tick_silence`** si tu veux l’autonomie « sans input » (timer côté serveur ou tâche périodique). |

**Persistance (optionnelle mais recommandée en prod) :**

- **RAM seule** : ok pour dev ; l’état disparaît au restart du process.
- **Session serveur** : Redis, fichier JSON par `session_id`, ou colonne en base — tu sérialises `engine.state.model_dump()` (Pydantic).
- **Mémoire longue** : déjà prévue via **`LongTermMemoryStore`** (JSONL ou extension future).

Sans persistance ni `tick_silence`, le moteur **existe** mais se comporte surtout comme un **module de suggestion au prochain message** : c’est déjà utile ; l’**autonomie** (relance sans message) suppose un **timer** + état conservé.

### 6.3 Comment il « communique avec nous » ?

Le moteur **ne parle pas** directement à l’utilisateur. Il produit des **artefacts de données** que **ton** UI ou **ton** client consomme :

1. **`ProactiveAction`** : texte `message`, type d’action (`question`, `suggestion`, `plan`, `autonomous_nudge`), mode courant, métadonnées.
2. **`integration_hints`** : petit dict JSON (mode, jauges, drapeaux du type « clarifier l’intention », « autoriser une relance autonome »).

**Canal habituel dans ton stack actuelle :**

- **Orchestrateur** `POST /v1/route` → le corps de réponse contient déjà `output` ([`RouteResponse`](../orchestrator/router/routes/route_intent.py)). Le greffon naturel consiste à **fusionner** dans `output` quelque chose comme :
  - `output["hybrid_proactive"] = { "action": action.model_dump(), "hints": hints }`
  - ou seulement `hints` si le texte proactif est injecté côté LLM dialogue plutôt qu’affiché brut.
- **Pilot (backend)** : si l’UI appelle le backend, qui proxy l’orchestrateur, la même structure arrive **same-origin** ; le front affiche une bannière, un second bulle, ou injecte le texte dans le champ de composition.

**Ce n’est pas** un WebSocket dédié au moteur hybride : tu peux réutiliser **le même** canal que celui qui porte déjà les réponses orchestrateur / dialogue. Si un jour tu veux des **push serveur → client** sans requête utilisateur, il faudra soit **WebSocket** / **SSE**, soit **poll** depuis le client sur `GET .../status` — c’est du **choix produit**, pas du paquet.

### 6.4 Cartographie rapide « fichier → responsabilité » (exemple orchestrateur)

| Fichier (indicatif) | Rôle du greffon |
|---------------------|-----------------|
| `orchestrator/pyproject.toml` | Dépendance vers `hybrid-proactive-agent`. |
| `orchestrator/router/routes/route_intent.py` (ou petit module `services/hybrid_proactive_adapters.py`) | Après classification / avant `invoke_after_route` : `observe_user_turn`, éventuellement `decide`, ajout au `output`. |
| `pilot_web` / assistant | Lire `output.hybrid_proactive` et afficher ou ignorer selon préférences. |

*(Les chemins exacts sont à figer quand tu implémentes ; le principe reste : un seul endroit qui possède l’instance `HybridProactiveEngine` par session.)*

---

## 7. Plus tard : demander des outils et agir

Le paquet **hybride proactif** ne remplace pas **`action_proposal`**, la **policy**, ni le **dispatch** vers `agent.desktop` / dialogue / MMO. La séparation saine :

| Couche | Rôle |
|--------|------|
| **Moteur hybride** | « J’ai une **intention interne** : clarifier, proposer un plan, relancer. » Sortie = **texte + hints** (et éventuellement un **label** du type d’initiative). |
| **Orchestrateur / capabilities** | « Cette initiative correspond-elle à une **capability** connue avec garde-fous ? » |
| **Action proposal + policy** | « On **propose** une action structurée (notepad, recherche, …) sans l’exécuter bêtement. » |
| **Humain ou approbation** | Exécution réelle (dry-run, jetons, etc.). |

**Deux patterns d’évolution possibles :**

1. **Proactif = suggestion textuelle uniquement**  
   Le moteur ajoute une question dans `output` ; l’utilisateur répond au clavier ; pas d’outil automatique.

2. **Proactif = amorce d’outil (recommandé pour l’action)**  
   Quand `decide()` retourne par exemple un type « je suggère d’ouvrir une proposition d’action », ton greffon appelle **`propose_action_from_text`** (ou équivalent) avec un texte **dérivé** de l’objectif interne, puis enchaîne le flux existant **soumis à la policy**. Le moteur hybride ne « tient » pas les clés API desktop : il **alimente** la même chaîne que l’utilisateur quand il tape « ouvre notepad ».

**Demander des outils sans les exécuter** : exposer dans `meta` de `ProactiveAction` un champ du type `requested_capability: "desktop_control"` + brouillon d’`action` — le **Pilot** affiche « L’agent propose : … » et l’utilisateur clique **Exécuter** → `POST /v1/action-proposal` ou route déjà en place.

En résumé : **communication** = JSON dans les réponses HTTP (et plus tard optionnellement push) ; **action** = **réutilisation** du chemin outillé existant, avec le moteur hybride comme **catalyseur d’intention**, pas comme exécuteur privilégié.
