"""
Hybrid Agent (modular): Supervisor + CodingSquad + Architect + Guardrail + Validator + MCP-only tools.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from langchain_core.messages import ToolMessage

from ollama_coder.core.config import RunConfig
from ollama_coder.core.mcp_loader import close_mcp_session
from ollama_coder.core.supervisor import build_graph


def parse_args():
    p = argparse.ArgumentParser(description="Hybrid Agent (Supervisor + Swarm + Architect + Guardrail + MCP)")
    p.add_argument("--task", dest="task", nargs="*", help="Task description")
    p.add_argument(
        "--check-command",
        default="pytest -q",
        help="Validator command; empty to disable",
    )
    p.add_argument("--max-loops", type=int, default=16)
    p.add_argument("--recursion-limit", type=int, default=80)
    p.add_argument("--coder-model", default="qwen2.5-coder:7b")
    p.add_argument("--reviewer-model", default="llama3.2")
    return p.parse_args()


def format_event(event):
    for node, data in event.items():
        if "messages" in data:
            last = data["messages"][-1]
            who = data.get("active_agent", node)
            if isinstance(last, ToolMessage):
                print(f"[{who}] TOOL → {last.content.strip()[:200]}")
            else:
                print(f"[{who}] → {last.content}")


def log_event(log_path: Path | None, event):
    if not log_path:
        return
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, default=str) + "\n")


def bootstrap_state(task: str, cfg: RunConfig):
    return {
        "messages": [("user", task)],
        "active_agent": "Coder",
        "loop_count": 0,
        "validator_ok": False,
        "blocked": False,
        "config": cfg,
    }


def main():
    args = parse_args()
    task = " ".join(args.task).strip() if args.task else ""
    if not task:
        task = input("Task: ")

    cfg = RunConfig(
        check_command=args.check_command or None,
        max_loops=args.max_loops,
        recursion_limit=args.recursion_limit,
        coder_model=args.coder_model,
        reviewer_model=args.reviewer_model,
    )

    app = asyncio.run(build_graph(cfg))

    print("🤖 Hybrid Agent ready")
    print(f"Validator: {cfg.check_command or 'disabled'} | Max loops: {cfg.max_loops}")

    initial_state = bootstrap_state(task, cfg)

    log_path = Path("logs/events.jsonl")

    async def runner():
        async for event in app.astream(
            initial_state,
            stream_mode="updates",
            config={"recursion_limit": cfg.recursion_limit},
        ):
            log_event(log_path, event)
            format_event(event)

    asyncio.run(runner())
    asyncio.run(close_mcp_session())


if __name__ == "__main__":
    main()
