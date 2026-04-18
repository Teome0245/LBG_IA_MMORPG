import pytest

from lbg_agents.dispatch import invoke_after_route


def test_dispatch_pm_stub() -> None:
    out = invoke_after_route(
        "agent.pm",
        actor_id="p:1",
        text="jalons projet et risques",
        context={"agent_site": "core"},
    )
    assert out.get("agent") == "pm_stub"
    brief = out.get("brief")
    assert isinstance(brief, dict)
    assert brief.get("title")
    assert isinstance(brief.get("hints"), list)
    assert out.get("agent_site") == "core"


def test_dispatch_pm_stub_includes_current_step_from_plan(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    plan = tmp_path / "plan_de_route.md"
    plan.write_text(
        "\n".join(
            [
                "# x",
                "",
                "**Étape actuelle** : faire A puis B.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("LBG_PM_PLAN_PATH", str(plan))
    out = invoke_after_route(
        "agent.pm",
        actor_id="p:1",
        text="plan de route",
        context={"pm_include_plan": True},
    )
    brief = out.get("brief")
    assert isinstance(brief, dict)
    assert brief.get("current_step_found") is True
    assert "Étape actuelle" in (brief.get("current_step") or "")


def test_dispatch_pm_stub_includes_milestones_and_tasks(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    plan = tmp_path / "plan_de_route.md"
    plan.write_text(
        "\n".join(
            [
                "# Plan test",
                "",
                "| Date | Changement notoire |",
                "| --- | --- |",
                "| 2026-01-01 | Ancien événement |",
                "| 2026-04-18 | **LAN** smoke vert |",
                "",
                "**Étape actuelle** : faire A; faire B — puis C.",
                "",
                "**File d’attente (intention produit)** : phase 2 — monter un worker.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("LBG_PM_PLAN_PATH", str(plan))
    out = invoke_after_route(
        "agent.pm",
        actor_id="p:1",
        text="jalons et tâches",
        context={},
    )
    brief = out.get("brief")
    assert isinstance(brief, dict)
    milestones = brief.get("milestones")
    assert isinstance(milestones, list)
    assert len(milestones) == 2
    assert milestones[-1].get("date") == "2026-04-18"
    assert "LAN" in (milestones[-1].get("summary") or "")
    tasks = brief.get("tasks")
    assert isinstance(tasks, list)
    titles = " ".join(str(t.get("title") or "") for t in tasks)
    assert "faire A" in titles
    assert "faire B" in titles
    assert "puis C" in titles
    assert "phase 2" in titles.lower()
    assert brief.get("file_attente_found") is True


def test_dispatch_pm_http_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    import lbg_agents.dispatch as dispatch_mod

    class _Resp:
        status_code = 200

        def json(self) -> dict:
            return {"agent": "pm_remote", "brief": {"title": "remote"}}

    class _ClientCtx:
        def __enter__(self) -> "_ClientCtx":
            return self

        def __exit__(self, *a: object) -> None:
            return None

        def post(self, url: str, json: dict | None = None) -> _Resp:
            assert url.endswith("/invoke")
            return _Resp()

    monkeypatch.setenv("LBG_AGENT_PM_URL", "http://127.0.0.1:8055")
    monkeypatch.setattr(dispatch_mod.httpx, "Client", lambda **kw: _ClientCtx())
    out = invoke_after_route("agent.pm", actor_id="p:1", text="roadmap", context={})
    assert out.get("agent") == "pm_remote"
