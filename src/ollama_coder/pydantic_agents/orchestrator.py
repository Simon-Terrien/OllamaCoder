from __future__ import annotations
from dataclasses import dataclass
from typing import Callable, Optional

from pydantic_ai import Agent, RunContext, AgentStreamEvent

from .models import DevPlan, OrchestrationSummary, CodeResult, DocsResult
from .planner_agent import planner_agent, PlannerDeps
from .coding_agent import coding_agent, CodingDeps
from .security_agent import security_agent, SecurityDeps
from .docs_agent import docs_agent, DocsDeps


@dataclass
class OrchestratorDeps:
    project_root: str
    apply_changes: bool = True


orchestrator_agent = Agent[OrchestratorDeps, OrchestrationSummary](
    "ollama:qwen2.5-coder:7b",
    deps_type=OrchestratorDeps,
    output_type=OrchestrationSummary,
    instructions=(
        "You orchestrate specialists. Call the planner, then execute steps with coding or security specialist; "
        "if docs are needed, call docs specialist. Return an OrchestrationSummary."
    ),
    defer_model_check=True,
)


@orchestrator_agent.instructions
async def orchestrator_dynamic_context(ctx: RunContext[OrchestratorDeps]) -> str:
    return (
        "You can call tools: call_planner, call_coding_specialist, call_security_specialist, call_docs_specialist. "
        f"apply_changes={ctx.deps.apply_changes!r}."
    )


@orchestrator_agent.tool
async def call_planner(ctx: RunContext[OrchestratorDeps], goal: str) -> DevPlan:
    deps = PlannerDeps(project_root=ctx.deps.project_root)
    res = await planner_agent.run(goal, deps=deps)
    return res.output


@orchestrator_agent.tool
async def call_coding_specialist(ctx: RunContext[OrchestratorDeps], step_description: str, specialty: str) -> CodeResult:
    deps = CodingDeps(
        project_root=ctx.deps.project_root,
        specialty=specialty,
        apply_changes=ctx.deps.apply_changes,
    )
    res = await coding_agent.run(step_description, deps=deps)
    return res.output


@orchestrator_agent.tool
async def call_security_specialist(ctx: RunContext[OrchestratorDeps], step_description: str) -> CodeResult:
    deps = SecurityDeps(
        project_root=ctx.deps.project_root,
        apply_changes=ctx.deps.apply_changes,
    )
    res = await security_agent.run(step_description, deps=deps)
    return res.output


@orchestrator_agent.tool
async def call_docs_specialist(ctx: RunContext[OrchestratorDeps], docs_context: str) -> DocsResult:
    deps = DocsDeps(
        project_root=ctx.deps.project_root,
        apply_changes=ctx.deps.apply_changes,
    )
    res = await docs_agent.run(docs_context, deps=deps)
    return res.output


async def stream_orchestration(
    user_goal: str,
    project_root: str,
    apply_changes: bool,
    on_event: Optional[Callable[[AgentStreamEvent], None]] = None,
):
    deps = OrchestratorDeps(project_root=project_root, apply_changes=apply_changes)
    async with orchestrator_agent.run_stream(user_goal, deps=deps) as run:
        async for event in run.stream_events():
            if on_event:
                on_event(event)
        return run.result.output  # type: ignore[return-value]
