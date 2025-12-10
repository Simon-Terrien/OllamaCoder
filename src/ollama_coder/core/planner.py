from __future__ import annotations
from typing import Annotated, TypedDict, List
import json
from langchain_ollama import ChatOllama
from langchain_core.messages import SystemMessage
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages

from .config import RunConfig


class PlanState(TypedDict, total=False):
    messages: Annotated[List, add_messages]
    plan: list
    step_index: int
    config: RunConfig
    needs_docs: bool


def create_planner(cfg: RunConfig):
    llm = ChatOllama(model=cfg.coder_model, format="json")

    PROMPT = (
        "Plan the task into 2-6 steps. Return JSON: {\"steps\":[{\"description\":str,\"specialty\":str}...],\"needs_docs\":bool}. "
        "Allowed specialties: backend, frontend, tests, devops, security, docs, general."
    )

    def planner_node(state: PlanState):
        resp = llm.invoke([SystemMessage(content=PROMPT)] + state["messages"])
        steps = []
        needs_docs = False
        try:
            data = json.loads(resp.content)
            steps = data.get("steps", []) or []
            needs_docs = bool(data.get("needs_docs", False))
        except Exception:
            pass
        return {
            "messages": [resp],
            "plan": steps,
            "step_index": 0,
            "needs_docs": needs_docs,
        }

    def after_planner(state: PlanState):
        if not state.get("plan"):
            return END
        return END

    wf = StateGraph(PlanState)
    wf.add_node("planner", planner_node)
    wf.add_edge(START, "planner")
    wf.add_edge("planner", END)
    return wf.compile()
