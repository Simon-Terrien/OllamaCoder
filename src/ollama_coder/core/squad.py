from __future__ import annotations
from typing import Annotated, Literal, TypedDict, List
from langchain_ollama import ChatOllama
from langchain_core.messages import SystemMessage
from langchain_core.tools import tool
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode

from .guardrail import guardrail_node
from .validator import validator_node
from .config import RunConfig


def _extract_tool_calls(text: str):
    """Best-effort parse of JSON tool call(s) from a text response."""
    if not text:
        return []
    import json
    import re

    # strip markdown fences
    cleaned = text.strip()
    cleaned = re.sub(r"^```[a-zA-Z]*", "", cleaned)
    cleaned = re.sub(r"```$", "", cleaned)

    try:
        obj = json.loads(cleaned)
    except Exception:
        return []

    calls = obj if isinstance(obj, list) else [obj]
    tool_calls = []
    for i, c in enumerate(calls):
        if not isinstance(c, dict):
            continue
        name = c.get("name")
        args = c.get("arguments") or c.get("args") or {}
        if name:
            tool_calls.append({"name": name, "args": args, "id": f"synthetic-{i}"})
    return tool_calls


class SquadState(TypedDict):
    messages: Annotated[List, add_messages]
    active_agent: Literal["Coder", "Reviewer"]
    loop_count: int
    validator_ok: bool
    blocked: bool
    config: RunConfig
    plan: list | None
    step_index: int | None


def create_squad(tools, cfg: RunConfig):
    @tool
    def transfer_to_reviewer():
        """Switch control to the reviewer agent."""
        return "Transfer to reviewer"

    @tool
    def transfer_to_coder():
        """Switch control to the coder agent."""
        return "Transfer to coder"

    @tool
    def squad_finished():
        """Mark the squad task as finished."""
        return "Squad finished"

    tools_ext = tools + [transfer_to_reviewer, transfer_to_coder, squad_finished]

    coder_llm = ChatOllama(model=cfg.coder_model, format="json").bind_tools(tools_ext)
    reviewer_llm = ChatOllama(model=cfg.reviewer_model, format="json").bind_tools(tools_ext)

    def coder_node(state: SquadState):
        prompt = (
            "You are the Coder. Write/modify files and run commands via tools. "
            "Always respond with tool calls, not prose. Do NOT wrap in markdown."
            "When you think code is ready, hand off to reviewer or rely on validator."
            f" apply_changes={state['config'].apply_changes if state.get('config') else True}."
        )
        resp = coder_llm.invoke([SystemMessage(content=prompt)] + state["messages"])
        if not getattr(resp, "tool_calls", None):
            maybe = _extract_tool_calls(resp.content)
            if maybe:
                resp.tool_calls = maybe
                resp.content = ""
        return {"messages": [resp], "active_agent": "Coder", "loop_count": state["loop_count"] + 1}

    def reviewer_node(state: SquadState):
        prompt = (
            "You are the Reviewer. Read and critique. Do NOT write files unless handing back. "
            "Always respond with tool calls or short text if approving."
            "If code looks good, call squad_finished or let validator confirm."
        )
        resp = reviewer_llm.invoke([SystemMessage(content=prompt)] + state["messages"])
        if not getattr(resp, "tool_calls", None):
            maybe = _extract_tool_calls(resp.content)
            if maybe:
                resp.tool_calls = maybe
                resp.content = ""
        return {"messages": [resp], "active_agent": "Reviewer", "loop_count": state["loop_count"] + 1}

    def after_agent(state: SquadState):
        last = state["messages"][-1]
        if hasattr(last, "tool_calls") and last.tool_calls:
            return "guardrail"
        return "validator"

    def after_guardrail(state: SquadState):
        return "agent" if state.get("blocked") else "tools"

    def after_tools(state: SquadState):
        # If tool returned an error, loop back to agent immediately
        last = state["messages"][-1]
        if hasattr(last, "content"):
            content = str(getattr(last, "content", "")).lower()
            if "error:" in content or "stderr" in content:
                return "agent"
        return "validator"

    def after_validator(state: SquadState):
        if state.get("validator_ok"):
            return END
        if state["loop_count"] >= cfg.max_loops:
            return END
        next_agent = "Reviewer" if state.get("active_agent") == "Coder" else "Coder"
        state["active_agent"] = next_agent
        state["step_index"] = (state.get("step_index") or 0) + 1
        return "agent"

    wf = StateGraph(SquadState)
    wf.add_node("agent", coder_node)
    wf.add_node("coder", coder_node)
    wf.add_node("reviewer", reviewer_node)
    wf.add_node("guardrail", guardrail_node)
    wf.add_node("tools", ToolNode(tools_ext))
    wf.add_node("validator", validator_node)

    wf.add_edge(START, "coder")
    wf.add_conditional_edges("coder", after_agent)
    wf.add_conditional_edges("reviewer", after_agent)
    wf.add_conditional_edges("guardrail", after_guardrail)
    wf.add_conditional_edges("tools", after_tools)
    wf.add_conditional_edges("validator", after_validator)

    wf.add_conditional_edges(
        "agent",
        lambda s: "reviewer" if s.get("active_agent") == "Reviewer" else "coder",
        {"coder": "coder", "reviewer": "reviewer"},
    )

    return wf.compile()
