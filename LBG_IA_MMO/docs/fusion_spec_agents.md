# Spécification agents unifiée (fusion — phase B)

Aligner les **deux familles** d’agents HTTP sans casser les dépôts sources : **LBG_IA** (`/execute`, `/capabilities`) et **LBG_IA_MMO** (`/invoke`, healthz). Ce document fixe un **contrat minimal** et un **mapping** pour une future **gateway** dans le monorepo.

**Références** : **`plan_fusion_lbg_ia.md`** §3.1, inventaire **`fusion_etat_des_lieux_v0.md`**.

---

## 1. Contrat minimal (cible produit)

Toute exécution d’agent derrière l’orchestration devrait pouvoir s’exprimer ainsi :

| Champ | Type | Rôle |
|-------|------|------|
| **`intent`** ou **`action_id`** | string | Intention métier ou id d’action (selon couche). |
| **`actor_id`** | string | Acteur (joueur, système, PNJ logique). |
| **`payload`** | objet | Paramètres spécifiques à l’agent (texte, ids, flags). |
| **`context`** | objet | `world_npc_id`, `lyra`, `quest_state`, `trace_id`, etc. |
| **`trace_id`** | string (optionnel) | Corrélation logs (`context._trace_id` côté MMO). |

La **réponse** inclut au minimum : **`ok`** ou équivalent, **`output`** (dict), et optionnellement **`lyra`**, erreurs typées.

---

## 2. LBG_IA_MMO (référence actuelle monorepo)

| Endpoint | Méthode | Rôle |
|----------|---------|------|
| **`/invoke`** | POST | Corps : intention + contexte ; réponse structurée par agent (dialogue, quêtes, combat…). |
| **`/healthz`** | GET | Santé du worker. |

Agents : **`lbg_agents`** — dispatch post‑routage orchestrateur (`CapabilitySpec`, `routed_to`).

---

## 3. LBG_IA (dépôt source — lecture)

| Endpoint | Méthode | Rôle |
|----------|---------|------|
| **`/execute`** | POST | Exécution générique (schéma `ExecuteRequest` / équivalent selon version). |
| **`/capabilities`** | GET | Capacités de l’agent. |
| **`/agents/{id}/run`** | POST | Lancement côté catalogue (souvent garde admin). |

Stub lab : **`/execute`** + **`/capabilities`** + **`/health`** (`scripts/lab_stub_agent.py`).

---

## 4. Table de correspondance

| Concept LBG_IA | Concept LBG_IA_MMO | Note |
|----------------|-------------------|------|
| `POST /execute` | `POST /invoke` | Même rôle sémantique : **faire faire** une action à l’agent. |
| `GET /capabilities` | `GET /healthz` + registry orchestrateur | MMO : capacités **centralisées** sur l’orchestrateur (`GET /v1/capabilities`) ; healthz **par** agent HTTP. |
| Corps `ExecuteRequest` | Corps route + `context` | Unifier vers **un** schéma JSON avec champ `context` étendu. |
| `POST /agents/{id}/run` | Routage orchestrateur + dispatch | Le **catalogue** LBG_IA devient un **profil** ; le MMO utilise **capabilities** + un seul `POST /v1/route`. |

---

## 5. Stratégie de convergence (sans big bang)

1. **Profil « jeu »** : conserver **`/invoke`** + contrats documentés dans **`agents/README.md`**.
2. **Profil « plateforme LBG_IA »** : lors du portage, exposer **`/invoke`** en interne quand l’ancien client envoie **`/execute`** (adaptateur).
3. **Gateway optionnelle** : un service **`/v1/agent-proxy/execute`** qui traduit vers **`/invoke`** des workers MMO — **une seule** couche de traduction.

---

## 6. Sécurité (rappel)

Modèle MMO : **DevOps** avec allowlist, **`LBG_DEVOPS_APPROVAL_TOKEN`**, audit JSONL. Modèle LBG_IA : **`require_admin`**, tokens divers. À l’union : **reprendre le niveau le plus strict** (déjà principe dans `plan_fusion_lbg_ia.md`).

---

## Voir aussi

- `fusion_spec_monde.md` — où vivent les PNJ « réseau » vs slice IA
- `fusion_pont_jeu_ia.md` — propagation du contexte jusqu’aux agents jeu
