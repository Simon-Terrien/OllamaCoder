from __future__ import annotations

import argparse
import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Iterable, List, Mapping, Sequence


@dataclass
class Viewpoint:
    name: str
    purpose: str
    stakeholders: List[str]
    concerns: List[str]


@dataclass
class View:
    name: str
    description: str
    elements: Mapping[str, Sequence[str]]


def _find_top_modules(root: Path, limit: int = 8) -> List[str]:
    src = root / "src" / "ollama_coder"
    if not src.exists():
        return []
    modules: List[str] = []
    for child in sorted(src.iterdir()):
        if child.is_dir() and not child.name.startswith("__"):
            modules.append(child.name)
        elif child.suffix == ".py":
            modules.append(child.name)
        if len(modules) >= limit:
            break
    return modules


def _list_scripts(pyproject: Path) -> List[str]:
    if not pyproject.exists():
        return []
    lines = pyproject.read_text(encoding="utf-8").splitlines()
    scripts: List[str] = []
    in_scripts = False
    for line in lines:
        if line.strip() == "[project.scripts]":
            in_scripts = True
            continue
        if in_scripts:
            if line.startswith("["):
                break
            if "=" in line:
                scripts.append(line.split("=", 1)[0].strip())
    return scripts


def build_architecture_description(root: Path) -> dict:
    system_name = root.name
    modules = _find_top_modules(root)
    scripts = _list_scripts(root / "pyproject.toml")

    stakeholders = [
        "Developers",
        "Operators",
        "Security",
        "Product/PM",
        "QA/Validation",
    ]

    concerns = [
        "Safety/Guardrails",
        "Reliability and self-correction",
        "Model/runtime cost",
        "Observability/logging",
        "Configurability (models, recursion limits)",
        "Batch throughput",
        "API compatibility (OpenAI-style, AG-UI)",
    ]

    viewpoints = [
        Viewpoint(
            name="Context",
            purpose="Show external actors and system boundary",
            stakeholders=stakeholders,
            concerns=["Scope", "External integrations", "Trust boundaries"],
        ),
        Viewpoint(
            name="Functional",
            purpose="Explain agent roles and behaviours",
            stakeholders=stakeholders,
            concerns=["Responsibilities", "Interactions", "Guardrails"],
        ),
        Viewpoint(
            name="Development",
            purpose="Show code structure and entrypoints",
            stakeholders=stakeholders,
            concerns=["Modularity", "Traceability", "Ownership"],
        ),
        Viewpoint(
            name="Runtime",
            purpose="How to run/deploy services",
            stakeholders=stakeholders,
            concerns=["Processes", "Ports", "Scaling", "Batch workers"],
        ),
        Viewpoint(
            name="Data",
            purpose="Identify key data/log artifacts",
            stakeholders=stakeholders,
            concerns=["Logs", "Artifacts", "State persistence"],
        ),
    ]

    views = {
        "context": View(
            name="Context view",
            description="System boundary with external actors and tools.",
            elements={
                "system": [system_name],
                "actors": [
                    "Human user / API client",
                    "Ollama models (coder/reviewer)",
                    "Filesystem + MCP server",
                    "External LLM endpoints (optional)",
                ],
                "interfaces": [
                    "FastAPI HTTP API (REST + /v1/chat/completions)",
                    "MCP tools: filesystem + run_command",
                ],
            },
        ),
        "functional": View(
            name="Functional/behaviour view",
            description="Key agents and their responsibilities.",
            elements={
                "agents": [
                    "Supervisor: routes tasks and orchestrates LangGraph state",
                    "CodingSquad: coder + reviewer loop",
                    "Architect: ISO-42010 docs & posture",
                    "DevOps: CI/CD, infra tasks",
                    "Planner: task breakdown",
                    "Validator: runs pytest (configurable)",
                    "Guardrail: blocks dangerous commands/paths",
                ]
            },
        ),
        "development": View(
            name="Development view",
            description="Codebase layout and entrypoints.",
            elements={
                "modules": modules,
                "entrypoints": scripts,
                "key_files": [
                    "src/ollama_coder/api.py (FastAPI)",
                    "src/ollama_coder/mcp_server.py (MCP tools)",
                    "src/ollama_coder/hybrid_agent.py (CLI hybrid agent)",
                ],
            },
        ),
        "runtime": View(
            name="Runtime view",
            description="Processes and deployment hints.",
            elements={
                "services": [
                    "FastAPI app via uvicorn (ollama_coder.api:app)",
                    "MCP server (stdio) for filesystem/run_command",
                    "Batch queue workers (async, SQLite-backed)",
                ],
                "ports": ["8000 (default FastAPI)"],
                "operations": [
                    "Start API: uv run python -m ollama_coder.api",
                    "Start MCP: uv run python -m ollama_coder.mcp_server",
                    "Run hybrid agent: uv run python -m ollama_coder.hybrid_agent --task \"...\"",
                ],
            },
        ),
        "data": View(
            name="Data/Info view",
            description="Persistent artifacts and logs.",
            elements={
                "stores": [
                    "logs/events.jsonl (runtime traces)",
                    "data/batch_jobs.db (batch queue persistence)",
                    "project/ (MCP sandbox root for generated files)",
                ]
            },
        ),
    }

    findings = [
        "Guardrails block destructive shell patterns and system paths.",
        "Validator defaults to pytest -q; set check_command=None to disable.",
        "Batch queue uses SQLite persistence and async workers.",
        "MCP server sandboxes file ops under project/ (configurable via OLLAMA_CODER_PROJECT_ROOT).",
    ]

    recommendations = [
        "Run uv run pytest -q before releases.",
        "Document model overrides when changing defaults.",
        "Keep batch DB and logs on durable storage if running long jobs.",
        "Expose FastAPI behind auth/proxy for multi-user setups.",
    ]

    description = {
        "system": {
            "name": system_name,
            "purpose": "Self-correcting multi-agent coding system with guardrails, FastAPI surface, batch queue, and MCP tools.",
            "root": str(root.resolve()),
        },
        "stakeholders": stakeholders,
        "concerns": concerns,
        "viewpoints": [asdict(vp) for vp in viewpoints],
        "views": {k: asdict(v) for k, v in views.items()},
        "findings": findings,
        "recommendations": recommendations,
        "metadata": {
            "source_root": str(root.resolve()),
        },
    }
    return description


def render_markdown(desc: Mapping[str, object]) -> str:
    lines: List[str] = []
    system = desc["system"]  # type: ignore[index]
    lines.append(f"# ISO 42010 Architecture Description — {system['name']}")  # type: ignore[index]
    lines.append("")
    lines.append(f"Purpose: {system['purpose']}")  # type: ignore[index]
    lines.append("")
    lines.append("## Stakeholders")
    for s in desc["stakeholders"]:  # type: ignore[index]
        lines.append(f"- {s}")
    lines.append("")
    lines.append("## Concerns")
    for c in desc["concerns"]:  # type: ignore[index]
        lines.append(f"- {c}")
    lines.append("")
    lines.append("## Viewpoints")
    for vp in desc["viewpoints"]:  # type: ignore[index]
        lines.append(f"- **{vp['name']}**: {vp['purpose']}")
    lines.append("")
    lines.append("## Views")
    views: Mapping[str, Mapping[str, Iterable[str]]] = desc["views"]  # type: ignore[assignment]
    for name, view in views.items():
        lines.append(f"### {view['name']}")  # type: ignore[index]
        lines.append(view["description"])  # type: ignore[index]
        elements: Mapping[str, Iterable[str]] = view["elements"]  # type: ignore[assignment]
        for bucket, items in elements.items():
            lines.append(f"- {bucket}:")
            for item in items:
                lines.append(f"  - {item}")
        lines.append("")
    lines.append("## Findings")
    for f in desc["findings"]:  # type: ignore[index]
        lines.append(f"- {f}")
    lines.append("")
    lines.append("## Recommendations")
    for r in desc["recommendations"]:  # type: ignore[index]
        lines.append(f"- {r}")
    lines.append("")
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a lightweight ISO 42010 architecture snapshot.")
    parser.add_argument("--root", type=str, default=".", help="Project root to analyze (default: .)")
    parser.add_argument(
        "--format", choices=["json", "markdown"], default="json", help="Output format (default: json)"
    )
    parser.add_argument("-o", "--output", type=str, help="Optional output file path.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    root = Path(args.root).resolve()
    desc = build_architecture_description(root)

    if args.format == "json":
        payload = json.dumps(desc, indent=2)
    else:
        payload = render_markdown(desc)

    if args.output:
        out_path = Path(args.output).expanduser()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(payload, encoding="utf-8")
    print(payload)


if __name__ == "__main__":
    main()
