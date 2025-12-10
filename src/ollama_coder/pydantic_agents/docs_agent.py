from __future__ import annotations
from dataclasses import dataclass
from pydantic_ai import Agent, RunContext
from .models import DocsResult
from .tools import write_file


@dataclass
class DocsDeps:
    project_root: str
    apply_changes: bool = True


docs_agent = Agent[DocsDeps, DocsResult](
    "ollama:qwen2.5-coder:7b",
    deps_type=DocsDeps,
    output_type=DocsResult,
    instructions=(
        "You are a documentation specialist. Produce concise docs updates. "
        "If asked, write docs files. Return DocsResult with summary and files_updated."
    ),
    defer_model_check=True,
)


@docs_agent.tool
def write_docs_file(ctx: RunContext[DocsDeps], path: str, content: str) -> str:
    if ctx.deps.apply_changes:
        write_file(ctx.deps.project_root, path, content)
    return path
