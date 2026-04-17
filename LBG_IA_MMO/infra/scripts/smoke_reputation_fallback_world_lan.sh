#!/usr/bin/env bash
set -euo pipefail

TIMEOUT_S="${LBG_SMOKE_TIMEOUT_S:-30}"
CORE="${LBG_SMOKE_CORE:-192.168.0.140:8000}"
MMO="${LBG_SMOKE_MMO:-192.168.0.245:8050}"
NPC_ID="${LBG_SMOKE_NPC_ID:-npc:merchant}"
DELTA="${LBG_SMOKE_REP_DELTA:-11}"
PILOT_TOKEN="${LBG_PILOT_INTERNAL_TOKEN:-}"
RESET_REP="${LBG_SMOKE_RESET_REP:-0}"

echo "=== Smoke LAN — réputation fallback monde (sans WS snapshot) ==="
echo "core=${CORE} mmo=${MMO} npc=${NPC_ID} delta=${DELTA} timeout_s=${TIMEOUT_S} reset_rep=${RESET_REP} token_present=$([[ -n "${PILOT_TOKEN}" ]] && echo 1 || echo 0)"

hdr_core=()
if [[ -n "${PILOT_TOKEN}" ]]; then
  hdr_core=(-H "X-LBG-Service-Token: ${PILOT_TOKEN}")
fi

get_rep_world () {
  out="$(
    curl -sS --max-time "${TIMEOUT_S}" \
      -w $'\n__HTTP_CODE__:%{http_code}\n' \
      "http://${MMO}/v1/world/lyra?npc_id=${NPC_ID}" || true
  )"
  OUT="${out}" python3 - <<'PY'
import os, json, sys
out = os.environ["OUT"]
marker = "\n__HTTP_CODE__:"
if marker not in out:
    print("ERREUR: réponse mmo_server inattendue (pas de code HTTP).", file=sys.stderr)
    print(out[:400], file=sys.stderr)
    raise SystemExit(1)
body, code = out.rsplit(marker, 1)
code = code.strip().splitlines()[0] if code else ""
if code != "200":
    print(f"ERREUR: mmo_server HTTP {code} (attendu 200).", file=sys.stderr)
    print("Body (début):", file=sys.stderr)
    print(body[:400], file=sys.stderr)
    raise SystemExit(1)
try:
    j = json.loads(body)
except Exception as e:
    print(f"ERREUR: JSON invalide depuis mmo_server: {e}", file=sys.stderr)
    print("Body (début):", file=sys.stderr)
    print(body[:400], file=sys.stderr)
    raise SystemExit(1)
v = (((j.get("lyra") or {}).get("meta") or {}).get("reputation") or {})
print(int(v.get("value") or 0))
PY
}

echo ""
echo "== 1) Reputation monde avant =="
before="$(get_rep_world)"
echo "reputation_world_before=${before}"

echo ""
if [[ "${RESET_REP}" == "1" ]]; then
  if [[ "${before}" != "0" ]]; then
    echo "== 2a) Reset réputation monde -> 0 (via backend, delta = -before) =="
    reset_delta="$((0 - before))"
    code="$(
      curl -sS --max-time "${TIMEOUT_S}" \
        -o /tmp/lbg_smoke_rep_fallback_body.txt \
        -w "%{http_code}" \
        -X POST "http://${CORE}/v1/pilot/reputation" \
        -H "Content-Type: application/json" \
        "${hdr_core[@]}" \
        -d "{\"npc_id\":\"${NPC_ID}\",\"delta\":${reset_delta}}" || true
    )"
    if [[ "${code}" != "200" ]]; then
      echo "ERREUR: reset backend /v1/pilot/reputation HTTP ${code} (attendu 200)" >&2
      head -c 400 /tmp/lbg_smoke_rep_fallback_body.txt >&2 || true
      exit 1
    fi
    after_reset="$(get_rep_world)"
    if [[ "${after_reset}" != "0" ]]; then
      echo "ERREUR: reset monde attendu 0, reçu ${after_reset}" >&2
      exit 1
    fi
    echo "OK: reset applied (world=0)"
    before="0"
  else
    echo "Reset demandé mais monde déjà à 0 : OK"
  fi
  echo ""
fi

echo "== 2) Commit delta via backend (/v1/pilot/reputation) =="
code="$(
  curl -sS --max-time "${TIMEOUT_S}" \
    -o /tmp/lbg_smoke_rep_fallback_body.txt \
    -w "%{http_code}" \
    -X POST "http://${CORE}/v1/pilot/reputation" \
    -H "Content-Type: application/json" \
    "${hdr_core[@]}" \
    -d "{\"npc_id\":\"${NPC_ID}\",\"delta\":${DELTA}}" || true
)"
if [[ "${code}" != "200" ]]; then
  echo "ERREUR: backend /v1/pilot/reputation HTTP ${code} (attendu 200)" >&2
  echo "" >&2
  echo "Body (début):" >&2
  head -c 400 /tmp/lbg_smoke_rep_fallback_body.txt >&2 || true
  echo "" >&2
  if [[ "${code}" == "401" ]]; then
    echo "Hint: le gate token est actif. Exporte LBG_PILOT_INTERNAL_TOKEN dans ton shell ou lance :" >&2
    echo "  LBG_PILOT_INTERNAL_TOKEN='...' LBG_SMOKE_TIMEOUT_S=${TIMEOUT_S} bash infra/scripts/smoke_reputation_fallback_world_lan.sh" >&2
  fi
  exit 1
fi
echo "OK: commit pilot envoyé"

echo ""
echo "== 3) Reputation monde après =="
after="$(get_rep_world)"
echo "reputation_world_after=${after}"

BEFORE="${before}" DELTA="${DELTA}" AFTER="${after}" python3 - <<'PY'
import os
before=int(os.environ["BEFORE"])
delta=int(os.environ["DELTA"])
after=int(os.environ["AFTER"])
expected=before+delta
expected=max(-100,min(100,expected))
assert after==expected, f"reputation monde attendu {expected}, reçu {after}"
print("OK: fallback monde cohérent")
PY

echo ""
echo "Smoke réputation fallback monde : OK"
