"""Tests du classifieur d'intention LLM (hybride + parsing)."""

from __future__ import annotations

import json
from unittest.mock import patch

from introspection.deterministic_classifier import DeterministicIntentClassifier
from introspection.llm_intent_classifier import (
    ALLOWED_INTENTS,
    classify_intent_llm,
    hybrid_classify,
    should_use_llm_intent,
)


def test_should_use_llm_context_deterministic() -> None:
    assert should_use_llm_intent({"_intent_classify": "deterministic"}) is False


def test_should_use_llm_context_llm() -> None:
    assert should_use_llm_intent({"_intent_classify": "LLM"}) is True


def test_hybrid_prefers_deterministic_when_llm_low_conf(monkeypatch) -> None:
    monkeypatch.delenv("LBG_ORCHESTRATOR_INTENT_LLM", raising=False)

    def fake_llm(_t: str):
        return ("npc_dialogue", 0.5, {"intent_source": "llm"})

    monkeypatch.setenv("LBG_ORCHESTRATOR_INTENT_LLM_BASE_URL", "http://fake")
    monkeypatch.setenv("LBG_ORCHESTRATOR_INTENT_LLM", "1")
    with patch("introspection.llm_intent_classifier.classify_intent_llm", fake_llm):
        det = DeterministicIntentClassifier()
        intent, conf, meta = hybrid_classify(
            "point d'avancement du produit",
            {},
            det.classify,
        )
    assert intent == "project_pm"
    assert meta.get("intent_source") == "deterministic"


def test_hybrid_uses_llm_when_deterministic_unknown(monkeypatch) -> None:
    monkeypatch.setenv("LBG_ORCHESTRATOR_INTENT_LLM", "1")
    monkeypatch.setenv("LBG_ORCHESTRATOR_INTENT_LLM_BASE_URL", "http://fake")

    def fake_llm(_t: str):
        return ("devops_probe", 0.82, {"intent_source": "llm", "assistant_reply": "Je lance un diagnostic."})

    with patch("introspection.llm_intent_classifier.classify_intent_llm", fake_llm):
        det = DeterministicIntentClassifier()
        intent, conf, meta = hybrid_classify(
            "vérifie si les services tournent encore",
            {},
            det.classify,
        )
    assert intent == "devops_probe"
    assert conf == 0.82
    assert meta.get("assistant_reply")


def test_hybrid_skips_llm_when_forced_deterministic(monkeypatch) -> None:
    monkeypatch.setenv("LBG_ORCHESTRATOR_INTENT_LLM", "1")
    monkeypatch.setenv("LBG_ORCHESTRATOR_INTENT_LLM_BASE_URL", "http://fake")

    def boom(_t: str):
        raise AssertionError("LLM should not be called")

    with patch("introspection.llm_intent_classifier.classify_intent_llm", boom):
        det = DeterministicIntentClassifier()
        intent, conf, meta = hybrid_classify(
            "vérifie si les services tournent encore",
            {"_intent_classify": "deterministic"},
            det.classify,
        )
    assert meta.get("intent_source") == "deterministic"


def test_classify_intent_llm_parses_json_body(monkeypatch) -> None:
    monkeypatch.setenv("LBG_ORCHESTRATOR_INTENT_LLM_BASE_URL", "http://127.0.0.1:9")

    fake_resp = {
        "choices": [
            {"message": {"content": '{"intent":"project_pm","confidence":0.88,"assistant_reply":"OK"}'}}
        ]
    }

    class CM:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return json.dumps(fake_resp).encode("utf-8")

    class R:
        def __init__(self):
            self.cm = CM()

        def __enter__(self):
            return self.cm

        def __exit__(self, *args):
            return False

    with patch("introspection.llm_intent_classifier.urllib.request.urlopen", return_value=R()):
        out = classify_intent_llm("hello")
    assert out is not None
    intent, conf, meta = out
    assert intent == "project_pm"
    assert meta.get("intent_source") == "llm"


def test_allowed_intents_excludes_risky() -> None:
    assert "desktop_control" not in ALLOWED_INTENTS
    assert "world_aid" not in ALLOWED_INTENTS
