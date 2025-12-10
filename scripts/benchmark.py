"""Quick benchmark runner for Ollama Coder.

Runs a list of tasks through the hybrid agent graph and records per-task metrics.
Requires Ollama models to be available. Results are written to JSONL for later
aggregation.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from typing import List

from ollama_coder.core.config import RunConfig
from ollama_coder.core.metrics import RunRecord, Timer, log_record, summarize_runs
from ollama_coder.core.supervisor import build_graph


def parse_args():
    p = argparse.ArgumentParser(description="Run simple benchmarks against the hybrid agent.")
    p.add_argument("tasks", nargs="*", help="Tasks to run. If empty, a small default suite is used.")
    p.add_argument("--output", default="logs/benchmark_results.jsonl", help="Path to write JSONL metrics.")
    p.add_argument("--max-loops", type=int, default=8, help="Max agent iterations per task.")
    p.add_argument("--check-command", default="pytest -q", help="Validator command; empty to disable.")
    p.add_argument("--coder-model", default="qwen2.5-coder:7b", help="Model for coder/supervisor.")
    p.add_argument("--reviewer-model", default="llama3.2", help="Model for reviewer.")
    p.add_argument("--recursion-limit", type=int, default=80, help="LangGraph recursion limit.")
    return p.parse_args()


def default_tasks() -> List[str]:
    return [
        "Add a unit test for guardrail to cover sudo block",
        "Write a README section on running batch jobs",
        "Refactor progress tracker to reduce duplicate code",
    ]


def bootstrap_state(task: str, cfg: RunConfig):
    return {
        "messages": [("user", task)],
        "active_agent": "Coder",
        "loop_count": 0,
        "validator_ok": False,
        "blocked": False,
        "config": cfg,
    }


async def run_task(app, task: str, cfg: RunConfig) -> RunRecord:
    state = bootstrap_state(task, cfg)
    with Timer() as t:
        final_state = await app.ainvoke(
            state,
            config={"recursion_limit": cfg.recursion_limit},
        )

    return RunRecord(
        task=task,
        duration_sec=t.seconds,
        validator_ok=bool(final_state.get("validator_ok")),
        blocked=bool(final_state.get("blocked")),
        loop_count=int(final_state.get("loop_count", 0)),
        plan_steps=len(final_state.get("plan", []) or []) if "plan" in final_state else None,
        model=cfg.coder_model,
    )


async def main():
    args = parse_args()
    tasks = args.tasks or default_tasks()

    cfg = RunConfig(
        check_command=args.check_command or None,
        max_loops=args.max_loops,
        recursion_limit=args.recursion_limit,
        coder_model=args.coder_model,
        reviewer_model=args.reviewer_model,
    )

    app = await build_graph(cfg)

    results = []
    for task in tasks:
        print(f"▶️  Running: {task}")
        record = await run_task(app, task, cfg)
        results.append(record.to_dict())
        log_record(record, Path(args.output))
        status = "✅" if record.validator_ok else "⚠️"
        print(f"   {status} {record.duration_sec:.2f}s loops={record.loop_count} blocked={record.blocked}")

    summary = summarize_runs(results)
    print("\nSummary")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
