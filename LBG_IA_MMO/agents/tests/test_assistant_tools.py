"""Tests assistant_tools."""

from __future__ import annotations

from lbg_agents.assistant_tools import infer_tools_from_text, parse_tool_calls_from_llm, strip_tool_tags


def test_infer_grep_from_question() -> None:
    tools = infer_tools_from_text("où est défini pilot_chat dans le code ?")
    assert any(t["name"] == "grep" for t in tools)


def test_infer_ssh_host() -> None:
    tools = infer_tools_from_text("diagnostic healthz sur linux-246")
    assert any(t["name"] == "ssh" and t["args"].get("server_id") == "linux-246" for t in tools)


def test_infer_core3_sonde() -> None:
    tools = infer_tools_from_text("sonde mmo core3 status")
    assert any(t["name"] == "core3" for t in tools)


def test_parse_tool_tags() -> None:
    raw = 'Réponse <lbg_tool>{"name":"grep","args":{"pattern":"foo"}}</lbg_tool> fin'
    calls = parse_tool_calls_from_llm(raw)
    assert calls[0]["name"] == "grep"
    assert strip_tool_tags(raw) == "Réponse  fin"
