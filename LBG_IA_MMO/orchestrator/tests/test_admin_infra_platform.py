"""Tests périmètre Atlas admin_infra (110/111/140/245/246 + front legacy optionnel)."""

from __future__ import annotations

from team.admin_infra_platform import (
    admin_infra_perimeter,
    audit_admin_infra_platform,
    audit_platform_host,
    platform_host_specs,
)


def test_perimeter_includes_111_light() -> None:
    assert admin_infra_perimeter() == ["110", "111", "140", "245", "246"]
    ids = {s["perimeter_id"] for s in platform_host_specs()}
    assert {"110", "111", "140", "245", "246"}.issubset(ids)


def test_platform_specs_dual_llm_labels(monkeypatch) -> None:
    monkeypatch.setenv("LBG_ATLAS_PROBE_FRONT_LEGACY", "1")
    specs = {s["id"]: s for s in platform_host_specs()}
    assert specs["llm_heavy_110"]["ollama_tier"] == "heavy"
    assert specs["llm_light_111"]["ollama_tier"] == "light"
    assert specs["front_legacy_112"]["required"] is False
    assert any(p["url"].endswith(":11434/api/tags") for p in specs["llm_light_111"]["probes"])


def test_audit_platform_host_marks_ko_on_probe_failure(monkeypatch) -> None:
    def fake_probe(url: str, *, timeout: float = 4.0) -> dict:
        return {"url": url, "ok": False, "error": "down"}

    monkeypatch.setattr("team.admin_infra_platform._probe_http", fake_probe)
    spec = {
        "id": "precu_245",
        "label": "PreCU",
        "host": "192.168.0.245",
        "perimeter_id": "245",
        "role": "precu_runtime",
        "required": True,
        "probes": [{"kind": "http", "url": "http://192.168.0.245:8050/healthz"}],
    }
    out = audit_platform_host(spec)
    assert out["ok"] is False
    assert out["perimeter_id"] == "245"


def test_audit_admin_infra_platform_structure(monkeypatch) -> None:
    monkeypatch.setenv("LBG_ATLAS_PROBE_FRONT_LEGACY", "0")
    monkeypatch.setattr(
        "team.admin_infra_platform.audit_ollama_lan",
        lambda **kw: {
            "ok": True,
            "track": "ollama_audit_dual_110_111",
            "recommendations": [],
            "gaps": [],
        },
    )
    monkeypatch.setattr(
        "team.admin_infra_platform.audit_platform_host",
        lambda spec: {
            "id": spec["id"],
            "perimeter_id": spec["perimeter_id"],
            "required": spec.get("required", True),
            "ok": spec["perimeter_id"] in ("110", "111", "140", "246"),
            "probes": [],
        },
    )
    out = audit_admin_infra_platform()
    assert out["track"] == "admin_infra_platform"
    assert out["hosts_total"] == 5
    assert "111" in out["perimeter"]
    assert "245" in out["perimeter"]
    assert any("245" in g for g in out.get("gaps") or [])
    assert out["topology"]["llm_light"].startswith("192.168.0.111")
