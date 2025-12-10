from __future__ import annotations

from dataclasses import dataclass

from pydantic_ai import Agent, RunContext

from .models import CodeResult, Patch
from .tools import list_files, read_file, run_tests, write_file


@dataclass
class CodingDeps:
    project_root: str
    specialty: str = "general"
    apply_changes: bool = True


coding_agent = Agent[CodingDeps, CodeResult](
    "ollama:qwen2.5-coder:7b",
    deps_type=CodingDeps,
    output_type=CodeResult,
    instructions=(
        "You are a coding specialist. Read minimal files, propose patches, and apply them when apply_changes is true. "
        "Return CodeResult with patches (final content). Keep edits small."
    ),
    defer_model_check=True,
)


@coding_agent.tool
def list_project_files(ctx: RunContext[CodingDeps], pattern: str = "**/*.py") -> list[str]:
    return list_files(ctx.deps.project_root, pattern)


@coding_agent.tool
def read_project_file(ctx: RunContext[CodingDeps], path: str) -> str:
    return read_file(ctx.deps.project_root, path)


@coding_agent.tool
def write_project_file(ctx: RunContext[CodingDeps], path: str, new_content: str) -> Patch:
    if ctx.deps.apply_changes:
        write_file(ctx.deps.project_root, path, new_content)
    return Patch(path=path, new_content=new_content)


@coding_agent.tool
def run_project_tests(ctx: RunContext[CodingDeps], cmd: str = "pytest -q") -> str:
    return run_tests(ctx.deps.project_root, cmd)
