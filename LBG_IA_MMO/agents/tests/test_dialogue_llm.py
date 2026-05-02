import pytest
import json

from lbg_agents.dialogue_llm import (
    DEFAULT_LBG_DIALOGUE_LLM_BASE_URL,
    DEFAULT_LBG_DIALOGUE_LLM_MODEL,
    build_system_prompt,
    base_url,
    is_configured,
    model_name,
    normalize_history,
    _sanitize_world_action,
)


def test_normalize_history_filters_and_caps() -> None:
    h = normalize_history(
        [
            {"role": "user", "content": "  Hi  "},
            {"role": "assistant", "content": "Salut."},
            {"role": "system", "content": "ignored"},
            "not-a-dict",
        ]
    )
    assert len(h) == 2
    assert h[0]["role"] == "user"
    assert h[1]["content"] == "Salut."


def test_default_ollama_when_llm_not_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LBG_DIALOGUE_LLM_DISABLED", raising=False)
    monkeypatch.delenv("LBG_DIALOGUE_LLM_BASE_URL", raising=False)
    monkeypatch.delenv("LBG_DIALOGUE_LLM_MODEL", raising=False)
    assert base_url() == DEFAULT_LBG_DIALOGUE_LLM_BASE_URL.rstrip("/")
    assert model_name() == DEFAULT_LBG_DIALOGUE_LLM_MODEL
    assert is_configured() is True


def test_resolve_route_fast_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    from lbg_agents import dialogue_llm as mod

    monkeypatch.setenv("LBG_DIALOGUE_FAST_ENABLED", "1")
    monkeypatch.setenv("LBG_DIALOGUE_FAST_BASE_URL", "https://api.groq.com/openai/v1")
    monkeypatch.setenv("LBG_DIALOGUE_FAST_MODEL", "llama-3.1-8b-instant")
    monkeypatch.setenv("LBG_DIALOGUE_FAST_API_KEY", "secret")

    route = mod._resolve_route({"dialogue_target": "fast"})
    assert route["target"] == "fast"
    assert route["base_url"] == "https://api.groq.com/openai/v1"
    assert route["model"] == "llama-3.1-8b-instant"


def test_resolve_route_fast_provider_resolves_api_key_reference(monkeypatch: pytest.MonkeyPatch) -> None:
    from lbg_agents import dialogue_llm as mod

    monkeypatch.setenv("GROQ_API_KEY", "secret-from-env")
    monkeypatch.setenv("LBG_DIALOGUE_FAST_ENABLED", "1")
    monkeypatch.setenv("LBG_DIALOGUE_FAST_BASE_URL", "https://api.groq.com/openai/v1")
    monkeypatch.setenv("LBG_DIALOGUE_FAST_MODEL", "llama-3.1-8b-instant")
    monkeypatch.setenv("LBG_DIALOGUE_FAST_API_KEY", "${GROQ_API_KEY}")

    route = mod._resolve_route({"dialogue_target": "fast"})
    assert route["api_key"] == "secret-from-env"


def test_resolve_route_fast_falls_back_to_local(monkeypatch: pytest.MonkeyPatch) -> None:
    from lbg_agents import dialogue_llm as mod

    monkeypatch.delenv("LBG_DIALOGUE_FAST_ENABLED", raising=False)
    monkeypatch.delenv("LBG_DIALOGUE_FAST_BASE_URL", raising=False)
    monkeypatch.delenv("LBG_DIALOGUE_FAST_MODEL", raising=False)
    monkeypatch.setenv("LBG_DIALOGUE_REMOTE_ENABLED", "0")

    route = mod._resolve_route({"dialogue_target": "fast"})
    assert route["target"] == "local"
    assert route["base_url"] == base_url()


def test_build_system_prompt_includes_scene() -> None:
    s = build_system_prompt(
        "Marc",
        {"scene": "Place du village", "world_hint": "Royaume d’Alder"},
    )
    assert "Marc" in s
    assert "Place du village" in s
    assert "Royaume" in s
    assert "Profil actif" in s


def test_build_system_prompt_includes_lyra_gauges() -> None:
    s = build_system_prompt(
        "Hagen",
        {
            "lyra": {
                "gauges": {"hunger": 0.5, "thirst": 0.2, "fatigue": 0.9},
                "version": "0.1",
            }
        },
    )
    assert "Hagen" in s
    assert "faim ~50%" in s
    assert "soif ~20%" in s
    assert "fatigue ~90%" in s
    assert "transparaître" in s
    assert "v0.1" in s


def test_build_system_prompt_omits_empty_lyra() -> None:
    s = build_system_prompt("X", {"lyra": {"version": "1"}})
    assert "Indicateurs internes" not in s


def test_build_system_prompt_includes_reputation_when_present() -> None:
    s = build_system_prompt(
        "Hagen",
        {"lyra": {"meta": {"reputation": {"value": 42}}}},
    )
    assert "Réputation locale" in s
    assert "42" in s


def test_build_system_prompt_uses_assistant_profile() -> None:
    s = build_system_prompt("Marc", {"dialogue_profile": "hal"})
    assert "HAL 9000" in s
    assert "Profil actif: hal" in s


def test_build_system_prompt_uses_mmo_profile_when_world_npc() -> None:
    s = build_system_prompt("Aerin", {"dialogue_profile": "chaleureux", "world_npc_id": "npc:innkeeper"})
    assert "Tu es Aerin chaleureux." in s
    assert "MMORPG multivers" in s


def test_build_system_prompt_honors_requested_world_action_kind(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LBG_DIALOGUE_WORLD_ACTIONS", "1")

    s = build_system_prompt(
        "Aerin",
        {
            "world_npc_id": "npc:innkeeper",
            "_require_action_json": True,
            "_world_action_kind": "quest",
        },
    )

    assert "kind='quest'" in s
    assert "obligatoirement" in s


def test_build_system_prompt_includes_npc_registry_context(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    from lbg_agents import dialogue_llm as mod

    reg = {
        "schema_version": 1,
        "npcs": [
            {
                "id": "npc:test",
                "name": "Testeur",
                "role": "scribe",
                "zone": "Archives",
                "faction": "Civils",
                "tone": "pedagogue",
                "summary": "Garde la trace des evenements.",
                "goals": ["tenir un registre"],
                "constraints": ["ne pas inventer de faits"],
            }
        ],
    }
    p = tmp_path / "npc_registry.json"
    p.write_text(json.dumps(reg), encoding="utf-8")
    monkeypatch.setenv("LBG_DIALOGUE_NPC_REGISTRY_PATH", str(p))
    mod._npc_registry_cache = None

    s = build_system_prompt("Testeur", {"world_npc_id": "npc:test"})
    assert "Profil PNJ (registre):" in s
    assert "Zone: Archives" in s
    assert "Objectifs:" in s
    mod._npc_registry_cache = None


def test_build_system_prompt_includes_race_and_bestiary_refs() -> None:
    from lbg_agents import dialogue_llm as mod
    from lbg_agents import world_content as wc

    mod._npc_registry_cache = None
    wc.reset_cache()
    s = build_system_prompt(
        "Maire",
        {
            "world_npc_id": "npc:mayor",
            "_creature_refs": ["creature:luporeve", "creature:inexistant"],
        },
    )
    assert "Race du personnage" in s
    assert "Humain" in s
    assert "Luporêve" in s
    assert "bestiaire" in s.lower() or "Créatures mentionnées" in s


def test_build_system_prompt_lyra_race_overrides_registry(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    from lbg_agents import dialogue_llm as mod
    from lbg_agents import world_content as wc

    d = tmp_path / "w"
    d.mkdir()
    (d / "races.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "races": [
                    {"id": "race:alpha", "display_name": "Alpha", "morphology": "M1", "lore_one_liner": "L1"},
                    {"id": "race:beta", "display_name": "Beta", "morphology": "M2", "lore_one_liner": "L2"},
                ],
            }
        ),
        encoding="utf-8",
    )
    (d / "creatures.json").write_text(json.dumps({"schema_version": 1, "creatures": []}), encoding="utf-8")
    monkeypatch.setenv("LBG_WORLD_CONTENT_DIR", str(d))
    wc.reset_cache()
    reg = {
        "schema_version": 1,
        "npcs": [
            {
                "id": "npc:duo",
                "name": "Test",
                "role": "x",
                "race_id": "race:alpha",
                "summary": "S",
            }
        ],
    }
    p = tmp_path / "npc_registry.json"
    p.write_text(json.dumps(reg), encoding="utf-8")
    monkeypatch.setenv("LBG_DIALOGUE_NPC_REGISTRY_PATH", str(p))
    mod._npc_registry_cache = None

    s_only_reg = build_system_prompt("T", {"world_npc_id": "npc:duo"})
    assert "Alpha" in s_only_reg

    s_lyra = build_system_prompt(
        "T",
        {"world_npc_id": "npc:duo", "lyra": {"meta": {"race_id": "race:beta"}}},
    )
    assert "Beta" in s_lyra
    assert "Alpha" not in s_lyra
    monkeypatch.delenv("LBG_WORLD_CONTENT_DIR", raising=False)
    monkeypatch.delenv("LBG_DIALOGUE_NPC_REGISTRY_PATH", raising=False)
    mod._npc_registry_cache = None
    wc.reset_cache()


def test_cache_key_changes_when_reputation_changes(monkeypatch: pytest.MonkeyPatch) -> None:
    # Activer le cache (sinon la clé n'est pas utilisée, mais on teste la fonction interne).
    from lbg_agents import dialogue_llm as mod

    c1 = {"lyra": {"meta": {"reputation": {"value": 1}}, "gauges": {"hunger": 0.1}}}
    c2 = {"lyra": {"meta": {"reputation": {"value": 2}}, "gauges": {"hunger": 0.1}}}
    k1 = mod._cache_key(speaker="PNJ", player_text="Salut", context=c1)
    k2 = mod._cache_key(speaker="PNJ", player_text="Salut", context=c2)
    assert k1 != k2


def test_sanitize_world_action_quest_completed() -> None:
    out = _sanitize_world_action(
        {"kind": "quest", "quest_id": "q:done", "quest_step": 2, "quest_accepted": True, "quest_completed": True}
    )
    assert out is not None
    assert out["quest_completed"] is True


def test_sanitize_world_action_quest_reputation() -> None:
    out = _sanitize_world_action(
        {
            "kind": "quest",
            "quest_id": "q:rep",
            "quest_step": 1,
            "quest_accepted": True,
            "reputation_delta": 12,
        }
    )
    assert out is not None
    assert out["reputation_delta"] == 12


def test_sanitize_world_action_quest_reputation_omit_when_zero() -> None:
    out = _sanitize_world_action(
        {
            "kind": "quest",
            "quest_id": "q:z",
            "quest_step": 0,
            "quest_accepted": True,
            "reputation_delta": 0,
        }
    )
    assert out is not None
    assert "reputation_delta" not in out
