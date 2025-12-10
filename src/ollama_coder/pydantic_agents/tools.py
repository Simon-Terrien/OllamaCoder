from __future__ import annotations

import subprocess
from pathlib import Path
from typing import List


def list_files(root: str, pattern: str = "**/*") -> List[str]:
    root_path = Path(root)
    return [str(p.relative_to(root_path)) for p in root_path.glob(pattern) if p.is_file()]


def read_file(root: str, path: str) -> str:
    p = Path(root) / path
    with p.open("r", encoding="utf-8") as f:
        return f.read()


def write_file(root: str, path: str, content: str) -> None:
    p = Path(root) / path
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8") as f:
        f.write(content)


def run_tests(root: str, cmd: str = "pytest -q") -> str:
    proc = subprocess.run(cmd, shell=True, cwd=root, capture_output=True, text=True, timeout=120)
    out = proc.stdout + "\n" + proc.stderr
    if proc.returncode != 0:
        return f"FAILED (exit {proc.returncode})\n" + out
    return out
