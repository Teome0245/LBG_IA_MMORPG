"""Évite les appels HTTP réels à Ollama pendant les tests (LLM désactivé par défaut)."""

import pytest


@pytest.fixture(autouse=True)
def disable_llm_for_tests(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LBG_DIALOGUE_LLM_DISABLED", "1")
