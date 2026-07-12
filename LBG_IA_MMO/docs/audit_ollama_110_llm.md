# Audit LLM local — VM 110 (Ollama H24)

**Date** : 2026-07-12  
**Hôte** : `192.168.0.110` — Pilot + Ollama (distinct du poste dev **10**)

---

## État matériel (audit live)

| Ressource | Valeur |
|-----------|--------|
| RAM | **23 Gi** (~22 Gi disponible) |
| GPU | **Aucun** (inférence CPU uniquement) |
| Ollama | `active` |
| Swap | 2 Gi |

---

## Modèles installés sur 110

| Modèle | Taille | Usage recommandé |
|--------|--------|------------------|
| `gemma4:e2b` | ~7 Go | **Forge Iris**, jobs planner, REASON rapide |
| `gemma4:26b` | ~17 Go | Dialogue PNJ, brief Thémis (qualité) |
| `gemma4-claude:latest` | ~17 Go | Variante 26b (alias fine-tune) |

Modèles **absents** (ne pas référencer dans lbg.env) : `phi4-mini`, `gemma3:4b`, `llama3.2` sauf après `ollama pull`.

---

## Matrice profils LBG (recommandée)

| Cas d'usage | Variable | Modèle 110 |
|-------------|----------|------------|
| Dialogue PNJ (local) | `LBG_DIALOGUE_LLM_MODEL` | `gemma4:26b` |
| Dialogue rapide (cloud) | `LBG_DIALOGUE_FAST_*` | Groq (failover → local) |
| Forge GDScript Iris | `LBG_REASON_MODEL_FORGE` | `gemma4:e2b` |
| Brief PM / synthèse | `LBG_REASON_MODEL_PM` | `gemma4:26b` |
| Jobs Cowork planner | `LBG_JOBS_PLANNER_LLM_MODEL` | `gemma4:e2b` |

---

## Tuning CPU (110 sans GPU)

```bash
# /etc/systemd/system/ollama.service.d/override.conf
[Service]
Environment=OLLAMA_MAX_LOADED_MODELS=1
Environment=OLLAMA_NUM_PARALLEL=1
```

Éviter de charger **26b + e2b** simultanément — risque swap.

Timeouts conseillés :
- `gemma4:e2b` : 45–90 s (forge)
- `gemma4:26b` : 180–300 s (dialogue)

---

## Audit automatisé

```bash
bash infra/scripts/audit_ollama_110_lan.sh
```

Module : `orchestrator/team/ollama_audit.py`  
Timer équipe : `lbg-team-ops-ollama-job` (toutes les 6 h) → tâche ops audit complète.

---

## Chaîne failover actuelle (lbg.env)

1. **Dialogue auto** : Groq fast → `gemma4:26b` local (`LBG_DIALOGUE_AUTO_ORDER=fast,local,remote`)
2. **REASON forge** : `gemma4:e2b` local → cloud si `LBG_REASON_FAILOVER=1`
3. **110** reste le socle H24 ; le poste **10** n'est pas requis

---

## Actions appliquées

- [x] Profils REASON par tâche (`forge` / `pm`)
- [x] Défauts alignés sur inventaire 110 (`gemma4:e2b` / `gemma4:26b`)
- [x] Audit intégré timer ops Ollama
- [ ] Optionnel : `OLLAMA_MAX_LOADED_MODELS=1` sur 110 (manuel systemd)
- [ ] Optionnel : palier `LBG_DIALOGUE_FAST_LOCAL_*` si Groq down
