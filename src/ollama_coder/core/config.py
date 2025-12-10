from __future__ import annotations

from dataclasses import dataclass


@dataclass
class RunConfig:
    check_command: str | None = "pytest -q"
    max_loops: int = 16
    recursion_limit: int = 80
    coder_model: str = "qwen2.5-coder:7b"
    reviewer_model: str = "llama3.2"
    apply_changes: bool = True
