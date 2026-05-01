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


def test_cache_key_changes_when_reputation_changes(monkeypatch: pytest.MonkeyPatch) -> None:
    # Activer le cache (sinon la clé n'est pas utilisée, mais on teste la fonction interne).
    from lbg_agents import dialogue_llm as mod

    c1 = {"lyra": {"meta": {"reputation": {"value": 1}}, "gauges": {"hunger": 0.1}}}
    c2 = {"lyra": {"meta": {"reputation": {"value": 2}}, "gauges": {"hunger": 0.1}}}
    k1 = mod._cache_key(speaker="PNJ", player_text="Salut", context=c1)
    k2 = mod._cache_key(speaker="PNJ", player_text="Salut", context=c2)
    assert k1 != k2
