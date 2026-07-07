# CLAUDE.md — LBG_IA_MMO (poste VM 140)

Documentation pour **Claude Code** sur `lbg-backend` (`/opt/LBG_IA_MMO`).

## Langue

Toutes les réponses en **français**, sauf demande contraire.

## Périmètre actuel (phase 1)

**Non-MMO uniquement** : backend, orchestrateur, agents, `pilot_shell`, infra LAN, deploy 110/140.

**Hors scope** sauf demande explicite : VM **245/246** (Core3 MMO), contenu monde, `mmmorpg_server` WS :7733.

## LLM

Claude Code est configuré pour **Ollama sur 110** (`gemma4:e2b` par défaut — plus rapide ; `gemma4-claude` via `LBG_CLAUDE_OLLAMA_MODEL` si besoin).

```bash
bash infra/scripts/claude_ollama_lan.sh work .
# ou alias : claude-lbg
```

## Commandes utiles

```bash
# Session persistante
lbg-tmux

# Claude dans le monorepo (Ollama LAN)
claude-lbg

# Deploy prod
bash infra/scripts/dev_pilot_workflow.sh --full

# Healthz
curl -s http://127.0.0.1:8000/healthz
```

## Structure

| Chemin | Rôle |
|--------|------|
| `backend/` | FastAPI pilot `:8000` |
| `orchestrator/` | Router IA `:8010` |
| `agents/` | Agents HTTP `:8020–8055` |
| `pilot_shell/` | UI React v2 (build → `pilot_web/v2/`) |
| `infra/scripts/` | deploy, bootstrap, workflows |
| `docs/` | topologie LAN, handoff, ops |

## Règles

- Ne pas lancer une 2ᵉ stack sur `:8000` (systemd prod).
- Ne pas commiter `infra/secrets/lbg.env` ni `node_modules`.
- Builds `npm run build` OK ; `npm run dev` réservé au WSL test `:5175`.
- UI prod : **110:8080** — API : **140:8000**.

## Références

- `docs/prompt_claude_140_non_mmo.md` — **prompt opérateur non-MMO** (à coller dans `claude-lbg`)
- `docs/handoff_windows_vers_vm140.md`
- `docs/fusion_env_lan.md`
- `docs/ops_vm_user.md`
