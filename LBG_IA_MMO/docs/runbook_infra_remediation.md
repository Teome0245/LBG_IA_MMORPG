# Remédiation infra — RAM et watchdog (Track C)

Playbook pour alertes mémoire LAN : sonde → plan → apply (approbation) → validate.

## Variables (`/etc/lbg-ia-mmo.env`)

| Variable | Défaut | Rôle |
|----------|--------|------|
| `LBG_VM_MEMORY_WARN_PCT` | `15` | Alerte si RAM dispo &lt; % |
| `LBG_VM_MEMORY_CRIT_PCT` | `8` | Critique si RAM dispo &lt; % |
| `LBG_INFRA_WATCHDOG_EXCLUDE_PRIME` | `0` sur timer 140 | `1` = ne pas sonder 246 |
| `LBG_REMEDIATION_PRIME_ENABLED` | `0` | `1` = proposer restart Prime dans le plan |
| `LBG_DEVOPS_SYSTEMD_RESTART_ALLOWLIST` | vide | Unités autorisées pour `systemd_restart` |
| `LBG_VM_MEMORY_WATCHDOG_RESTART` | `0` sur **246** | `1` = restart local via script bash |

Unités suggérées par label (override : `LBG_REMEDIATION_HOST_UNITS`) :

```
prime=lbg-core3-prime.service,precu=lbg-core3-precu.service,front=nginx.service,core=lbg-orchestrator.service
```

## 1. Sonde manuelle (VM 140 — orchestrateur)

```bash
cd /opt/LBG_IA_MMO
PYTHONPATH=agents/src .venv/bin/python -m lbg_agents.infra_watchdog
```

Exit code : `0` ok, `1` warn, `2` critical.

JSON avec plan si warn/critical :

```bash
bash infra/scripts/run_infra_watchdog.sh --json
```

## 2. Plan remédiation RAM (lecture seule)

Via DevOps :

```json
{"kind": "memory_remediation_plan"}
```

Ou remédiation :

```json
{"step": "plan", "source": "memory"}
```

Le plan liste des actions **sans les exécuter**. Un restart Prime n’apparaît que si `LBG_REMEDIATION_PRIME_ENABLED=1`.

## 3. Apply restart (approbation obligatoire)

Prérequis :

1. `LBG_DEVOPS_SYSTEMD_RESTART_ALLOWLIST` contient l’unité (ex. `lbg-core3-prime.service`)
2. `context.devops_approval` renseigné (hors dry-run)
3. Fenêtre maintenance / quota DevOps respectés

```json
{
  "step": "apply",
  "devops_action": {"kind": "systemd_restart", "unit": "lbg-core3-prime.service"}
}
```

**Note** : `systemd_restart` via orchestrateur **140** ne redémarre que des services **locaux** à 140. Pour **Prime (246)**, utiliser :

```bash
ssh lbg@192.168.0.246 'bash /opt/LBG_IA_MMO/infra/scripts/watch_vm_memory_health.sh --json'
```

Avec restart auto sur 246 (approbation humaine = activer la variable) :

```bash
# Sur 246 uniquement — jamais depuis le LLM sans garde-fou
LBG_VM_MEMORY_WATCHDOG_RESTART=1 bash infra/scripts/watch_vm_memory_health.sh
```

## 4. Timer watchdog (VM 140)

```bash
bash infra/scripts/install_infra_watchdog_vm.sh
systemctl list-timers | grep infra-watchdog
```

État persisté : `/var/lib/lbg/infra_watchdog/state.json` (inclut `remediation_plan` si alerte).

## 5. Validation

```json
{"step": "validate"}
```

Ou re-sonde :

```json
{"kind": "infra_watchdog"}
```

## Flux recommandé

```
infra_watchdog (warn/critical)
    → remediation_plan dans state.json
    → opérateur lit suggested_actions
    → remediation_apply + devops_approval (si restart)
    → infra_watchdog validate
```

## Références

- `agents/src/lbg_agents/infra_memory_remediation.py`
- `agents/src/lbg_agents/infra_watchdog.py`
- `infra/scripts/watch_vm_memory_health.sh` (local Prime)
- [`runbook_ops_bots_watchdog.md`](runbook_ops_bots_watchdog.md)
