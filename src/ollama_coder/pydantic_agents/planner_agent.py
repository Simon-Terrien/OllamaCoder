from __future__ import annotations

from dataclasses import dataclass

from pydantic_ai import Agent, RunContext

from .models import DevPlan


@dataclass
class PlannerDeps:
    project_root: str


planner_agent = Agent[PlannerDeps, DevPlan](
    "ollama:qwen2.5-coder:7b",
    deps_type=PlannerDeps,
    output_type=DevPlan,
    instructions=(
        "You are a senior planner. Produce a DevPlan with concise steps. "
        "Each step must include a specialty: backend, frontend, tests, devops, security, docs, or general. "
        "Prefer 2-6 small steps."
    ),
    defer_model_check=True,  # Defer model check to allow running without Ollama
)


@planner_agent.instructions
async def dynamic_ctx(ctx: RunContext[PlannerDeps]) -> str:
    return f"Project root is {ctx.deps.project_root}."
