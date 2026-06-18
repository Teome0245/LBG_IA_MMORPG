# Pont IA Core3 — routage LLM (alignement orchestrateur)

## Qui fait quoi ?

| Couche | Rôle |
|--------|------|
| **Orchestrateur** (`:8010`, VM 140) | Classifie l’**intention** (`npc_dialogue`, `quest`, …) et route vers un **agent** ; injecte `dialogue_target` pour le dialogue PNJ. |
| **`dialogue_llm`** (agents) | Choisit le **palier LLM** : `local` (Ollama), `fast` (Groq, etc.), `remote`, ou `auto` (`LBG_DIALOGUE_AUTO_ORDER`). |
| **Sidecar pont IA** (`:8791`, VM 245) | Pilote **Lia** via Core3 ; **ne passe pas** par `/v1/route` aujourd’hui, mais lit les **mêmes variables** `LBG_DIALOGUE_*` que `dialogue_llm` (`/etc/lbg-ia-mmo.env`). |

Le sidecar n’est pas un dialogue PNJ : l’intention « bot Core3 » n’existe pas encore côté orchestrateur (évolution Phase C+). En attendant, **`CORE3_IA_DIALOGUE_TARGET=auto`** + `/etc/lbg-ia-mmo.env` alignent les **clés et URLs** sur le reste de la stack LBG.

## Configuration (VM 245)

1. **`/etc/lbg-ia-mmo.env`** — source de vérité (comme sur 140) :
   - `LBG_DIALOGUE_FAST_ENABLED=1`
   - `LBG_DIALOGUE_FAST_BASE_URL`, `LBG_DIALOGUE_FAST_API_KEY` (Groq)
   - `LBG_DIALOGUE_LLM_BASE_URL` → Ollama 110 (fallback `local`)
   - `GROQ_API_KEY`, `OPENAI_API_KEY`, etc.

2. **`/etc/lbg-core3-ia.env`** — spécifique pont IA :
   ```bash
   CORE3_IA_DIALOGUE_TARGET=auto
   # ou fast | local | remote
   ```

3. **systemd** `lbg-core3-ia-sidecar` charge les deux fichiers + `PYTHONPATH=/opt/LBG_IA_MMO/agents/src`.

```bash
bash infra/scripts/configure_core3_ia_llm_vm.sh auto
sudo systemctl restart lbg-core3-ia-sidecar
curl -s http://127.0.0.1:8791/healthz | python3 -m json.tool
```

`healthz` expose `llm_routes` : liste des paliers essayés (sans clés API).

## Ordre `auto` (défaut sidecar)

`LBG_DIALOGUE_AUTO_ORDER` (défaut agents : `local,fast,remote`) — le sidecar en mode `auto` essaie en pratique **`fast,local,remote`** pour privilégier Groq avant Ollama lent.

En cas d’échec (403, timeout), le palier suivant est tenté.

## Régénérer les clés

Si Groq renvoie **403** : mettre à jour `GROQ_API_KEY` (ou `LBG_DIALOGUE_FAST_API_KEY`) dans `/etc/lbg-ia-mmo.env`, puis redémarrer le sidecar. Même procédure que pour Pilot / agents dialogue sur 140.

## Phase C — orchestrateur

Intent **`core3_bot_action`** → `agent.core3` → `POST` sidecar (`/v1/npc-think`, `/v1/think`).

Variable : **`LBG_CORE3_IA_SIDECAR_URL`** (ex. `http://192.168.0.245:8791` si le sidecar écoute sur le LAN).

Doc : **`docs/core3_ia_phase_c_npc_pilots.md`**.
