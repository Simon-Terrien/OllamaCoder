from __future__ import annotations

import json
from typing import Annotated, List, TypedDict

from langchain_core.messages import SystemMessage
from langchain_ollama import ChatOllama
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages

from .architect import create_architect
from .config import RunConfig
from .devops import create_devops
from .mcp_loader import get_mcp_tools
from .planner import create_planner
from .squad import create_squad


class SupState(TypedDict, total=False):
    messages: Annotated[List, add_messages]
    next: str
    loop_count: int
    active_agent: str
    validator_ok: bool
    blocked: bool
    config: RunConfig
    plan: list
    step_index: int
    needs_docs: bool
    current_specialty: str
    steps_done: int


def supervisor_node(state: SupState):
    cfg = state.get("config")
    model = cfg.coder_model if cfg else "qwen2.5-coder:7b"
    llm = ChatOllama(model=model, format="json")
    sys_prompt = (
        "You are a Supervisor.\n"
        "Routing rules:\n"
        "- If the user asks for architecture, ISO-42010, security posture, risks, documentation: route to Architect.\n"
        "- If the user asks for CI/CD, Docker, containers, Kubernetes, Helm, deployment pipelines, infra-as-code: "
        "route to DevOps.\n"
        "- If the user asks for coding or tests on application code: route to CodingSquad.\n"
        "- If the user asks to plan, roadmap, or break down tasks: route to Planner.\n"
        "- If a plan exists, dispatch each step in order; map specialties: devops->DevOps, security->Architect, "
        "docs->Architect, tests/backend/frontend/general->CodingSquad.\n"
        "- Otherwise: FINISH.\n"
        'Return JSON only: {"next": "Planner" | "Architect" | "DevOps" | "CodingSquad" | "FINISH"}'
    )
    res = llm.invoke([SystemMessage(content=sys_prompt)] + state["messages"])
    try:
        decision = json.loads(res.content).get("next", "FINISH")
    except Exception:
        decision = "FINISH"
    return {
        "next": decision,
        "loop_count": state.get("loop_count", 0),
        "active_agent": state.get("active_agent", "Coder"),
        "validator_ok": state.get("validator_ok", False),
        "blocked": state.get("blocked", False),
        "config": state.get("config"),
        "plan": state.get("plan", []),
        "step_index": state.get("step_index", 0),
        "needs_docs": state.get("needs_docs", False),
        "current_specialty": state.get("current_specialty", ""),
    }


def build_graph(cfg: RunConfig):
    async def _build():
        tools = await get_mcp_tools()
        squad = create_squad(tools, cfg)
        architect = create_architect(tools, cfg)
        devops = create_devops(tools, cfg)
        planner = create_planner(cfg)

        wf = StateGraph(SupState)
        wf.add_node("Supervisor", supervisor_node)
        wf.add_node("Planner", planner)
        wf.add_node("CodingSquad", squad)
        wf.add_node("Architect", architect)
        wf.add_node("DevOps", devops)

        wf.add_edge(START, "Supervisor")
        wf.add_conditional_edges(
            "Supervisor",
            lambda s: s["next"],
            {
                "Planner": "Planner",
                "CodingSquad": "CodingSquad",
                "Architect": "Architect",
                "DevOps": "DevOps",
                "FINISH": END,
            },
        )
        wf.add_edge("Planner", "Supervisor")
        wf.add_edge("Architect", "Supervisor")
        wf.add_edge("DevOps", "Supervisor")
        wf.add_edge("CodingSquad", "Supervisor")

        return wf.compile()

    return _build()
