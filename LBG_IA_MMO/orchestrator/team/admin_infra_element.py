"""Alertes Element Atlas — périmètre hôtes KO (110/111/140/245/246)."""

from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path
from typing import Any


def alerts_enabled() -> bool:
    if os.environ.get("LBG_ADMIN_INFRA_PERIMETER_ALERT_DISABLE", "0").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    ):
        return False
    return os.environ.get("LBG_ADMIN_INFRA_PERIMETER_ALERT", "1").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


def alert_state_path() -> Path:
    raw = os.environ.get(
        "LBG_ADMIN_INFRA_PERIMETER_ALERT_STATE",
        "/var/lib/lbg/team_admin_infra/perimeter_alert_state.json",
    ).strip()
    return Path(raw)


def alert_cooldown_s() -> float:
    try:
        return max(300.0, float(os.environ.get("LBG_ADMIN_INFRA_PERIMETER_ALERT_COOLDOWN_S", "3600")))
    except ValueError:
        return 3600.0


def load_env_file(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if not path.is_file():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s or s.startswith("#") or "=" not in s:
            continue
        key, val = s.split("=", 1)
        out[key.strip()] = val.strip().strip('"').strip("'")
    return out


def perimeter_has_ko(platform: dict[str, Any]) -> bool:
    hosts_ok = int(platform.get("hosts_ok") or 0)
    hosts_total = int(platform.get("hosts_total") or 0)
    if hosts_total and hosts_ok < hosts_total:
        return True
    gaps = platform.get("gaps")
    return isinstance(gaps, list) and len(gaps) > 0


def perimeter_ko_signature(platform: dict[str, Any]) -> str:
    failed_ids: list[str] = []
    hosts = platform.get("hosts") if isinstance(platform.get("hosts"), list) else []
    for h in hosts:
        if isinstance(h, dict) and not h.get("ok"):
            failed_ids.append(str(h.get("perimeter_id") or h.get("id") or "?"))
    gaps = platform.get("gaps") if isinstance(platform.get("gaps"), list) else []
    payload = {"failed": sorted(failed_ids), "gaps": gaps[:20]}
    return json.dumps(payload, sort_keys=True, ensure_ascii=False)


def format_perimeter_ko_message(platform: dict[str, Any]) -> str:
    lines = [
        "⚠️ Atlas — périmètre LLM / runtime KO",
        "",
        f"• hôtes OK : {platform.get('hosts_ok')}/{platform.get('hosts_total')}",
        f"• périmètre : {', '.join(platform.get('perimeter') or [])}",
        "",
    ]
    hosts = platform.get("hosts") if isinstance(platform.get("hosts"), list) else []
    for h in hosts:
        if not isinstance(h, dict):
            continue
        mark = "OK" if h.get("ok") else "KO"
        lines.append(f"• [{mark}] {h.get('perimeter_id')} — {h.get('label')} ({h.get('host')})")
        if not h.get("ok"):
            probes = h.get("probes") if isinstance(h.get("probes"), list) else []
            for p in probes:
                if isinstance(p, dict) and not p.get("ok"):
                    err = str(p.get("error") or p.get("status") or "probe failed")[:120]
                    lines.append(f"    - {p.get('url')}: {err}")

    gaps = platform.get("gaps") if isinstance(platform.get("gaps"), list) else []
    if gaps:
        lines.append("")
        lines.append("Écarts config / Ollama :")
        for g in gaps[:8]:
            lines.append(f"• {g}")

    lines.extend(
        [
            "",
            "Action : corriger le(s) hôte(s) KO avant bench long ou routage agentique.",
        ]
    )
    return "\n".join(lines)[:5500]


def _load_alert_state() -> dict[str, Any]:
    path = alert_state_path()
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _save_alert_state(payload: dict[str, Any]) -> None:
    path = alert_state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def should_send_perimeter_alert(platform: dict[str, Any], *, state: dict[str, Any] | None = None) -> bool:
    if not perimeter_has_ko(platform):
        return False
    st = state if state is not None else _load_alert_state()
    sig = perimeter_ko_signature(platform)
    last_sig = str(st.get("last_signature") or "")
    last_ts = float(st.get("last_alert_ts") or 0)
    if sig != last_sig:
        return True
    return not last_ts or (time.time() - last_ts) >= alert_cooldown_s()


def send_element_message(message: str) -> dict[str, Any]:
    p03_root = Path(os.environ.get("LBG_P03_ROOT", "/opt/lbg_project_03"))
    p03_py = p03_root / ".venv/bin/python"
    env_file = Path(os.environ.get("LBG_P03_ENV", "/etc/lbg-project-03.env"))
    if not p03_py.is_file():
        return {"ok": False, "error": f"p03 venv absent: {p03_py}"}

    env = os.environ.copy()
    env.update(load_env_file(env_file))
    env["PYTHONPATH"] = str(p03_root)
    code = (
        "from lbg_agents.matrix_config import MatrixConfig\n"
        "from lbg_agents.matrix_client import MatrixClient\n"
        "import os, sys\n"
        "msg = os.environ.get('ATLAS_ADMIN_INFRA_MSG', '')\n"
        "cfg = MatrixConfig.from_env()\n"
        "if not cfg.configured:\n"
        "    print({'ok': False, 'error': 'matrix_not_configured'}); sys.exit(1)\n"
        "out = MatrixClient(cfg.homeserver, access_token=cfg.access_token, user_id=cfg.user_id)"
        ".send_text(cfg.room_id, msg)\n"
        "print(out); sys.exit(0 if out.get('ok') else 1)\n"
    )
    proc = subprocess.run(
        [str(p03_py), "-c", code],
        env={**env, "ATLAS_ADMIN_INFRA_MSG": message[:5500]},
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    if proc.returncode != 0:
        return {"ok": False, "stderr": (proc.stderr or "")[-500:], "stdout": (proc.stdout or "")[-500:]}
    lines = [ln for ln in (proc.stdout or "").strip().splitlines() if ln.strip()]
    if not lines:
        return {"ok": True, "raw": ""}
    try:
        return json.loads(lines[-1])
    except json.JSONDecodeError:
        return {"ok": True, "raw": (proc.stdout or "")[-200:]}


def maybe_notify_perimeter_ko(platform: dict[str, Any]) -> dict[str, Any]:
    """Envoie Element si un hôte du périmètre est KO (avec cooldown / signature)."""
    if not alerts_enabled():
        return {"skipped": True, "reason": "LBG_ADMIN_INFRA_PERIMETER_ALERT=0"}

    if not perimeter_has_ko(platform):
        _save_alert_state({"last_clear_ts": time.time(), "last_signature": ""})
        return {"skipped": True, "reason": "perimeter_ok"}

    state = _load_alert_state()
    if not should_send_perimeter_alert(platform, state=state):
        return {
            "skipped": True,
            "reason": "cooldown_or_same_signature",
            "signature": perimeter_ko_signature(platform),
        }

    msg = format_perimeter_ko_message(platform)
    out = send_element_message(msg)
    if out.get("ok"):
        _save_alert_state(
            {
                "last_alert_ts": time.time(),
                "last_signature": perimeter_ko_signature(platform),
                "hosts_ok": platform.get("hosts_ok"),
                "hosts_total": platform.get("hosts_total"),
            }
        )
    return {"ok": bool(out.get("ok")), "element": out, "signature": perimeter_ko_signature(platform)}
