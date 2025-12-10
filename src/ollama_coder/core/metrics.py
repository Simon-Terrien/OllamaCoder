"""Lightweight metrics helpers for benchmarking runs."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from statistics import mean, median
from typing import Iterable, List, Dict, Any
import json
import time


@dataclass
class RunRecord:
    task: str
    duration_sec: float
    validator_ok: bool
    blocked: bool
    loop_count: int
    plan_steps: int | None = None
    model: str | None = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task": self.task,
            "duration_sec": round(self.duration_sec, 3),
            "validator_ok": self.validator_ok,
            "blocked": self.blocked,
            "loop_count": self.loop_count,
            "plan_steps": self.plan_steps,
            "model": self.model,
        }


def log_record(record: RunRecord, path: Path) -> None:
    """Append a single run record to a JSONL file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record.to_dict()) + "\n")


def summarize_runs(records: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    """Aggregate basic metrics from run records.

    Expects dictionaries with keys: duration_sec, validator_ok, blocked, loop_count.
    Missing keys are treated as falsy/zero where applicable.
    """

    recs: List[Dict[str, Any]] = list(records)
    if not recs:
        return {
            "count": 0,
            "successes": 0,
            "success_rate": 0.0,
            "avg_duration_sec": 0.0,
            "median_duration_sec": 0.0,
            "avg_loops": 0.0,
            "blocked": 0,
        }

    durations = [float(r.get("duration_sec", 0.0)) for r in recs]
    loops = [int(r.get("loop_count", 0)) for r in recs]
    successes = [bool(r.get("validator_ok", False)) for r in recs]
    blocked = [bool(r.get("blocked", False)) for r in recs]

    return {
        "count": len(recs),
        "successes": sum(successes),
        "success_rate": round(sum(successes) / len(recs), 3),
        "avg_duration_sec": round(mean(durations), 3),
        "median_duration_sec": round(median(durations), 3),
        "avg_loops": round(mean(loops), 2),
        "blocked": sum(blocked),
    }


class Timer:
    """Simple context manager to measure wall-clock duration."""

    def __enter__(self):
        self.start = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc, tb):
        self.end = time.perf_counter()
        self.duration = self.end - self.start

    @property
    def seconds(self) -> float:
        return getattr(self, "duration", 0.0)

