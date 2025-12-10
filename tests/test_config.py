"""Tests for RunConfig dataclass."""

from ollama_coder.core.config import RunConfig


def test_default_config():
    """Test default RunConfig values."""
    cfg = RunConfig()
    assert cfg.check_command == "pytest -q"
    assert cfg.max_loops == 16
    assert cfg.recursion_limit == 80
    assert cfg.coder_model == "qwen2.5-coder:7b"
    assert cfg.reviewer_model == "llama3.2"
    assert cfg.apply_changes


def test_custom_config():
    """Test custom RunConfig values."""
    cfg = RunConfig(
        check_command="make test",
        max_loops=10,
        recursion_limit=50,
        coder_model="codellama:7b",
        reviewer_model="mistral:7b",
        apply_changes=False,
    )
    assert cfg.check_command == "make test"
    assert cfg.max_loops == 10
    assert cfg.recursion_limit == 50
    assert cfg.coder_model == "codellama:7b"
    assert cfg.reviewer_model == "mistral:7b"
    assert not cfg.apply_changes


def test_none_check_command():
    """Test that check_command can be None."""
    cfg = RunConfig(check_command=None)
    assert cfg.check_command is None
