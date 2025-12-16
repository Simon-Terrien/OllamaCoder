from __future__ import annotations

from ollama_coder.core import supervisor as sup
from ollama_coder.core.config import RunConfig


class DummyResponse:
    content = '{"next": "Planner"}'


class DummyLLM:
    def __init__(self, *_, **__):
        pass

    def invoke(self, _messages):
        return DummyResponse()


def test_supervisor_routes_planned_steps(monkeypatch):
    class FailLLM:
        def __init__(self, *_, **__):
            raise AssertionError("LLM should not run when plan exists")

    monkeypatch.setattr(sup, "ChatOllama", FailLLM)

    plan = [
        {"description": "Set up infrastructure", "specialty": "devops"},
        {"description": "Implement feature", "specialty": "backend"},
    ]
    base_state = {"messages": [], "plan": plan, "step_index": 0, "config": RunConfig()}

    first = sup.supervisor_node(base_state)
    assert first["next"] == "DevOps"
    assert first["step_index"] == 1
    assert first["current_specialty"] == "devops"

    second = sup.supervisor_node({**base_state, **first})
    assert second["next"] == "CodingSquad"
    assert second["step_index"] == 2
    assert second["current_specialty"] == "backend"

    finished = sup.supervisor_node({**base_state, **second})
    assert finished["next"] == "FINISH"
    assert finished["steps_done"] == len(plan)


def test_supervisor_routes_ad_hoc_tasks(monkeypatch):
    monkeypatch.setattr(sup, "ChatOllama", DummyLLM)

    result = sup.supervisor_node({"messages": [], "config": RunConfig()})

    assert result["next"] == "Planner"
    assert result["plan"] == []
    assert result["step_index"] == 0
