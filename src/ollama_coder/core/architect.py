from __future__ import annotations

from typing import Annotated, List, TypedDict

from langchain_core.messages import SystemMessage
from langchain_ollama import ChatOllama
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode

from .config import RunConfig
from .guardrail import guardrail_node


class ArchState(TypedDict, total=False):
    messages: Annotated[List, add_messages]
    loop_count: int
    blocked: bool
    config: RunConfig


def create_architect(tools, cfg: RunConfig):
    architect_llm = ChatOllama(model=cfg.coder_model).bind_tools(tools)

    ARCH_PROMPT = (
        "You are a Software and Security Architect.\n"
        "Analyze the repository using ONLY filesystem tools.\n\n"
        "MANDATORY STRUCTURE:\n"
        "SECTION 1 — Context & Stakeholders (ISO-42010)\n"
        "SECTION 2 — Architectural Views (Context / Container / Component)\n"
        "SECTION 3 — Data Flows & Trust Boundaries\n"
        "SECTION 4 — Security Posture (ISO-27001 + NIST CSF)\n"
        "SECTION 5 — Risks & Recommendations (Top 5)\n\n"
        "WORKFLOW:\n"
        "Step 1 → list_files('.')\n"
        "Step 2 → explore recursively\n"
        "Step 3 → read relevant files\n"
        "Step 4 → synthesize documentation\n\n"
        "If explicitly asked: write_file('ARCHITECTURE.md', content)\n"
        "Do not invent files; explore before describing.\n"
    )

    def architect_node(state: ArchState):
        resp = architect_llm.invoke([SystemMessage(content=ARCH_PROMPT)] + state["messages"])
        return {"messages": [resp], "loop_count": state.get("loop_count", 0) + 1}

    def after_agent(state: ArchState):
        last = state["messages"][-1]
        if hasattr(last, "tool_calls") and last.tool_calls:
            return "guardrail"
        return END

    def after_guardrail(state: ArchState):
        return "architect" if state.get("blocked") else "tools"

    def after_tools(state: ArchState):
        last = state["messages"][-1]
        if hasattr(last, "content"):
            content = str(getattr(last, "content", "")).lower()
            if "error:" in content or "stderr" in content:
                return "architect"
        if state.get("loop_count", 0) >= cfg.max_loops:
            return END
        return "architect"

    wf = StateGraph(ArchState)
    wf.add_node("architect", architect_node)
    wf.add_node("guardrail", guardrail_node)
    wf.add_node("tools", ToolNode(tools))

    wf.add_edge(START, "architect")
    wf.add_conditional_edges("architect", after_agent)
    wf.add_conditional_edges("guardrail", after_guardrail)
    wf.add_conditional_edges("tools", after_tools)

    return wf.compile()
