"""Tests for metrics helper functions."""

from ollama_coder.core.metrics import RunRecord, summarize_runs


def test_summarize_runs_empty():
    summary = summarize_runs([])
    assert summary["count"] == 0
    assert summary["success_rate"] == 0.0


def test_summarize_runs_values():
    records = [
        RunRecord(task="a", duration_sec=1.0, validator_ok=True, blocked=False, loop_count=2).to_dict(),
        RunRecord(task="b", duration_sec=3.0, validator_ok=False, blocked=True, loop_count=4).to_dict(),
        RunRecord(task="c", duration_sec=2.0, validator_ok=True, blocked=False, loop_count=3).to_dict(),
    ]

    summary = summarize_runs(records)

    assert summary["count"] == 3
    assert summary["successes"] == 2
    assert summary["success_rate"] == round(2 / 3, 3)
    assert summary["avg_duration_sec"] == 2.0
    assert summary["median_duration_sec"] == 2.0
    assert summary["avg_loops"] == 3.0
    assert summary["blocked"] == 1
