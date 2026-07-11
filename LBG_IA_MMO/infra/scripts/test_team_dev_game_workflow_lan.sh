#!/usr/bin/env bash
# Test LAN — workflow dev_game (brief + action_proposal forge) et chaîne QA→followup simulée.
#
# Usage :
#   bash infra/scripts/test_team_dev_game_workflow_lan.sh
#   LBG_ORCHESTRATOR_URL=http://192.168.0.140:8010 bash infra/scripts/test_team_dev_game_workflow_lan.sh
#   bash infra/scripts/test_team_dev_game_workflow_lan.sh --full-chain   # SSH 140 : QA failed → followup

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ORCH="${LBG_ORCHESTRATOR_URL:-http://192.168.0.140:8010}"
ORCH="${ORCH%/}"
FULL_CHAIN=0

for arg in "$@"; do
  case "$arg" in
    --full-chain) FULL_CHAIN=1 ;;
  esac
done

echo "=== Test dev_game workflow (orchestrateur ${ORCH}) ==="

CREATE=$(curl -sf -X POST "${ORCH}/v1/team/tasks" \
  -H 'Content-Type: application/json' \
  -d '{
    "role": "dev_game",
    "objective": "Analyser échec smoke — prototype sandbox dry-run correctif gameplay Core3",
    "actor_id": "system:test_dev_game_workflow",
    "context": {
      "dev_game_focus": true,
      "_qa_followup": true,
      "parent_task_id": "test-qa-parent",
      "qa_failure_summary": {"smoke_ok": false, "smoke_exit_code": 1, "kind": "qa_smoke"}
    }
  }')
TASK_ID=$(python3 -c "import json,sys; print(json.load(sys.stdin)['id'])" <<<"${CREATE}")
echo "Tâche dev_game créée : ${TASK_ID}"

RUN=$(curl -sf -X POST "${ORCH}/v1/team/tasks/${TASK_ID}/run" -H 'Content-Type: application/json' -d '{}')
echo "${RUN}" > /tmp/lbg_test_dev_game_run.json
python3 <<'PY'
import json
with open("/tmp/lbg_test_dev_game_run.json", encoding="utf-8") as f:
    run = json.load(f)
assert run.get("status") == "done", run
res = run.get("result") or {}
assert res.get("kind") == "dev_game_workflow", res
prop = res.get("action_proposal") or {}
assert prop.get("capability") == "prototype_game", prop
assert prop.get("source") == "team_dev_game", prop
print("OK dev_game_workflow + action_proposal prototype_game (team_dev_game)")
print("summary:", (prop.get("summary") or "")[:120])
PY

if [[ "${FULL_CHAIN}" == "1" ]]; then
  echo ""
  echo "=== Chaîne QA failed → followup (sur VM core via Python) ==="
  CORE_HOST="${LBG_CORE_VM_HOST:-192.168.0.140}"
  ssh -o ConnectTimeout=8 "lbg@${CORE_HOST}" 'bash -s' <<'EOF'
set -euo pipefail
cd /opt/LBG_IA_MMO
export PYTHONPATH=orchestrator:agents/src:.
export LBG_TEAM_DB_PATH="${LBG_TEAM_DB_PATH:-/var/lib/lbg-ia-mmo/team_tasks.db}"
/opt/LBG_IA_MMO/.venv/bin/python3 <<'PY'
from team import store as team_store
from team import roles as team_roles
from team.qa_followup import maybe_spawn_after_qa_failure, auto_run_followup_tasks

task = team_store.create_task(role="qa", objective="test smoke KO simulé", actor_id="system:test_qa_chain")
team_store.update_task(
    task.id,
    status="failed",
    result={
        "kind": "qa_smoke",
        "ok": False,
        "smoke_script": {"ok": False, "exit_code": 99, "skipped": False},
    },
)
refreshed = team_store.get_task(task.id)
assert refreshed
ids = maybe_spawn_after_qa_failure(refreshed)
assert len(ids) >= 3, ids
roles = {team_store.get_task(i).role for i in ids if team_store.get_task(i)}
assert "pm" in roles and "dev_game" in roles and "ops" in roles, roles
auto_run_followup_tasks(ids)
pm = [t for t in team_store.list_tasks(role="pm", actor_id="system:team_qa_followup") if t.id in ids]
assert pm and pm[0].status == "done", pm[0].status if pm else None
dev_tasks = [team_store.get_task(i) for i in ids if team_store.get_task(i) and team_store.get_task(i).role == "dev_game"]
print("OK chaîne followup:", ids)
print("PM auto-run status:", pm[0].status)
print("dev_game task (queued):", dev_tasks[0].id if dev_tasks else None)
PY
EOF
fi

echo ""
echo "=== Test player_ia probe (246 sidecar) ==="
CREATE2=$(curl -sf -X POST "${ORCH}/v1/team/tasks" \
  -H 'Content-Type: application/json' \
  -d '{
    "role": "player_ia",
    "objective": "Vérifier joueurs IA Prime 246",
    "actor_id": "system:test_player_ia"
  }')
TASK2=$(python3 -c "import json,sys; print(json.load(sys.stdin)['id'])" <<<"${CREATE2}")
RUN2=$(curl -sf -X POST "${ORCH}/v1/team/tasks/${TASK2}/run" -H 'Content-Type: application/json' -d '{}')
echo "${RUN2}" > /tmp/lbg_test_player_ia_run.json
python3 <<'PY'
import json
with open("/tmp/lbg_test_player_ia_run.json", encoding="utf-8") as f:
    run = json.load(f)
res = run.get("result") or {}
print("player_ia status:", run.get("status"), "ok:", res.get("ok"), "online:", res.get("online_count"))
if run.get("status") != "done" and res.get("ok") is not True:
    raise SystemExit("player_ia probe KO — vérifier sidecar 246:8791 et bots Lia/Nix")
print("OK player_ia probe")
PY

echo ""
echo "=== Test player_ia think L2 (approbation) ==="
CREATE3=$(curl -sf -X POST "${ORCH}/v1/team/tasks" \
  -H 'Content-Type: application/json' \
  -d '{
    "role": "player_ia",
    "objective": "Tick autonomie Lia think",
    "actor_id": "system:test_think",
    "context": {"player_ia_mode": "think_tick", "player_id": "lia"}
  }')
echo "${CREATE3}" > /tmp/lbg_test_think_create.json
python3 <<'PY'
import json, os, subprocess
with open("/tmp/lbg_test_think_create.json") as f:
    c = json.load(f)
assert c.get("approval_required") is True, c
print("OK think task requires L2 approval:", c.get("id"))
PY

echo ""
echo "=== Test pm brief réunification ==="
CREATE4=$(curl -sf -X POST "${ORCH}/v1/team/tasks" \
  -H 'Content-Type: application/json' \
  -d '{
    "role": "pm",
    "objective": "Brief réunification sous-projets",
    "actor_id": "system:test_pm_reunif",
    "context": {"reunification_brief": true}
  }')
TASK4=$(python3 -c "import json,sys; print(json.load(sys.stdin)['id'])" <<<"${CREATE4}")
RUN4=$(curl -sf -X POST "${ORCH}/v1/team/tasks/${TASK4}/run" -H 'Content-Type: application/json' -d '{}')
echo "${RUN4}" > /tmp/lbg_test_pm_reunif_run.json
python3 <<'PY'
import json
with open("/tmp/lbg_test_pm_reunif_run.json", encoding="utf-8") as f:
    run = json.load(f)
assert run.get("status") == "done", run
res = run.get("result") or {}
assert res.get("kind") == "pm_brief", res
assert res.get("reunification") is True, res
out = res.get("output") or {}
brief = out.get("brief") or {}
subs = brief.get("subprojects") or []
assert len(subs) >= 5, subs
print("OK pm_brief réunification —", len(subs), "sous-projets")
PY

echo ""
echo "=== Test godot supervisor (équipe autonome) ==="
CREATE5=$(curl -sf -X POST "${ORCH}/v1/team/tasks" \
  -H 'Content-Type: application/json' \
  -d '{
    "role": "qa",
    "objective": "Supervise client Godot — sidecar 246 + lbg-ws/2",
    "actor_id": "system:test_godot_supervisor",
    "context": {"godot_supervisor": true, "godot_mode": "full"}
  }')
TASK5=$(python3 -c "import json,sys; print(json.load(sys.stdin)['id'])" <<<"${CREATE5}")
RUN5=$(curl -sf -X POST "${ORCH}/v1/team/tasks/${TASK5}/run" -H 'Content-Type: application/json' -d '{}')
echo "${RUN5}" > /tmp/lbg_test_godot_supervisor_run.json
python3 <<'PY'
import json
with open("/tmp/lbg_test_godot_supervisor_run.json", encoding="utf-8") as f:
    run = json.load(f)
assert run.get("status") == "done", run
res = run.get("result") or {}
assert res.get("kind") == "godot_supervisor", res
assert res.get("ok") is True, res
tracks = {t.get("track") for t in (res.get("tracks") or []) if isinstance(t, dict)}
assert "sidecar_m1" in tracks and "lbg_ws2_readiness" in tracks, tracks
assert "infographiste_assets" in tracks, tracks
print("OK godot_supervisor — tracks:", sorted(tracks))
PY

echo ""
echo "=== Test infographiste workflow (Pygmalion / dev_game) ==="
CREATE6=$(curl -sf -X POST "${ORCH}/v1/team/tasks" \
  -H 'Content-Type: application/json' \
  -d '{
    "role": "dev_game",
    "objective": "Audit pipeline assets GLB Infographiste IA",
    "actor_id": "system:test_infographiste",
    "context": {"infographiste_ia": true, "subproject": "infographiste_ia"}
  }')
TASK6=$(python3 -c "import json,sys; print(json.load(sys.stdin)['id'])" <<<"${CREATE6}")
RUN6=$(curl -sf -X POST "${ORCH}/v1/team/tasks/${TASK6}/run" -H 'Content-Type: application/json' -d '{}')
echo "${RUN6}" > /tmp/lbg_test_infographiste_run.json
python3 <<'PY'
import json
with open("/tmp/lbg_test_infographiste_run.json", encoding="utf-8") as f:
    run = json.load(f)
assert run.get("status") == "done", run
res = run.get("result") or {}
assert res.get("kind") == "infographiste_workflow", res
assert res.get("ok") is True, res
assert res.get("persona") == "Pygmalion", res
probe = res.get("probe") or {}
assert probe.get("kind") == "infographiste_probe", probe
prop = res.get("action_proposal") or {}
assert prop.get("source") == "team_infographiste_ia", prop
print("OK infographiste_workflow — glb_expected:", probe.get("glb_expected"))
PY

echo ""
echo "Tout vert — voir #/team sur http://192.168.0.110:8080/#/team"
