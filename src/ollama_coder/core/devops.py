from __future__ import annotations

from typing import Annotated, List, TypedDict

from langchain_core.messages import SystemMessage
from langchain_ollama import ChatOllama
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode

from .config import RunConfig
from .guardrail import guardrail_node


def _extract_tool_calls(text: str):
    """Best-effort parse of JSON tool call(s) from a text response."""
    if not text:
        return []
    import json
    import re

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
            tool_calls.append({"name": name, "args": args, "id": f"devops-{i}"})
    return tool_calls


class DevOpsState(TypedDict, total=False):
    messages: Annotated[List, add_messages]
    loop_count: int
    blocked: bool
    config: RunConfig
    plan: list | None
    step_index: int | None


def create_devops(tools, cfg: RunConfig):
    """Create DevOps agent subgraph (CI/CD, Docker, infra)."""
    devops_llm = ChatOllama(model=cfg.coder_model, format="json").bind_tools(tools)

    DEVOPS_PROMPT = (
        "You are a DevOps / Platform Engineer.\n"
        "Use ONLY the provided filesystem and run_command tools.\n"
        "Always respond with tool calls (JSON), not prose, when making changes.\n\n"
        "You can:\n"
        "- Create or modify Dockerfiles, docker-compose.yaml, Kubernetes manifests.\n"
        "- Set up CI/CD pipelines (GitHub Actions, GitLab CI, etc.).\n"
        "- Add scripts for build, test, lint, packaging.\n"
        "- Run commands to validate configs (e.g., pytest, docker build, kubectl lint).\n\n"
        "WORKFLOW:\n"
        "1) list_files('.') to understand repo.\n"
        "2) read_file(...) to inspect current configs.\n"
        "3) write_file(...) to add/update infra/CI files.\n"
        "4) run_command(...) to validate where appropriate.\n\n"
        "apply_changes may be false; in that case, describe patches but do NOT skip tool calls.\n"
        "NEVER execute destructive commands or touch system paths; rely on guardrails.\n"
    )

    def devops_node(state: DevOpsState):
        resp = devops_llm.invoke([SystemMessage(content=DEVOPS_PROMPT)] + state["messages"])
        if not getattr(resp, "tool_calls", None):
            maybe = _extract_tool_calls(getattr(resp, "content", ""))
            if maybe:
                resp.tool_calls = maybe
                resp.content = ""
        return {"messages": [resp], "loop_count": state.get("loop_count", 0) + 1}

    def after_agent(state: DevOpsState):
        last = state["messages"][-1]
        if hasattr(last, "tool_calls") and last.tool_calls:
            return "guardrail"
        return END

    def after_guardrail(state: DevOpsState):
        return "devops" if state.get("blocked") else "tools"

    def after_tools(state: DevOpsState):
        last = state["messages"][-1]
        if hasattr(last, "content"):
            content = str(getattr(last, "content", "")).lower()
            if "error:" in content or "stderr" in content:
                return "devops"
        if state.get("loop_count", 0) >= cfg.max_loops:
            return END
        state["step_index"] = (state.get("step_index") or 0) + 1
        return "devops"

    wf = StateGraph(DevOpsState)
    wf.add_node("devops", devops_node)
    wf.add_node("guardrail", guardrail_node)
    wf.add_node("tools", ToolNode(tools))

    wf.add_edge(START, "devops")
    wf.add_conditional_edges("devops", after_agent)
    wf.add_conditional_edges("guardrail", after_guardrail)
    wf.add_conditional_edges("tools", after_tools)

    return wf.compile()
