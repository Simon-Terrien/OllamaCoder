from __future__ import annotations
from dataclasses import dataclass
from pydantic_ai import Agent, RunContext
from .models import CodeResult, Patch
from .tools import list_files, read_file, write_file, run_tests


@dataclass
class SecurityDeps:
    project_root: str
    apply_changes: bool = True


security_agent = Agent[SecurityDeps, CodeResult](
    "ollama:qwen2.5-coder:7b",
    deps_type=SecurityDeps,
    output_type=CodeResult,
    instructions=(
        "You are a security specialist. Focus on securing code, configs, dependencies. "
        "Make minimal, safe changes. Return CodeResult with patches."
    ),
    defer_model_check=True,
)


@security_agent.tool
def list_project_files(ctx: RunContext[SecurityDeps], pattern: str = "**/*.py") -> list[str]:
    return list_files(ctx.deps.project_root, pattern)


@security_agent.tool
def read_project_file(ctx: RunContext[SecurityDeps], path: str) -> str:
    return read_file(ctx.deps.project_root, path)


@security_agent.tool
def write_project_file(ctx: RunContext[SecurityDeps], path: str, new_content: str) -> Patch:
    if ctx.deps.apply_changes:
        write_file(ctx.deps.project_root, path, new_content)
    return Patch(path=path, new_content=new_content)


@security_agent.tool
def run_project_tests(ctx: RunContext[SecurityDeps], cmd: str = "pytest -q") -> str:
    return run_tests(ctx.deps.project_root, cmd)
