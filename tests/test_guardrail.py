"""Tests for the guardrail security module."""

from ollama_coder.core.guardrail import (
    BLOCKED_CMD_SUBSTR,
    SYSTEM_PATH_PREFIXES,
    guardrail_node,
)


class MockToolCall:
    def __init__(self, name: str, args: dict, call_id: str = "test-id"):
        self.name = name
        self.args = args
        self.id = call_id

    def get(self, key, default=None):
        return getattr(self, key, default)

    def __getitem__(self, key):
        return getattr(self, key)


class MockMessage:
    def __init__(self, tool_calls=None, content=""):
        self.tool_calls = tool_calls or []
        self.content = content


def test_guardrail_allows_safe_commands():
    """Test that guardrail allows safe commands."""
    msg = MockMessage(
        tool_calls=[
            {"name": "run_command", "args": {"command": "pytest -q"}, "id": "safe-1"},
        ]
    )
    state = {"messages": [msg]}
    result = guardrail_node(state)
    assert not result["blocked"]
    assert result["messages"] == []


def test_guardrail_blocks_rm_command():
    """Test that guardrail blocks rm commands."""
    msg = MockMessage(
        tool_calls=[
            {
                "name": "run_command",
                "args": {"command": "rm -rf /tmp/test"},
                "id": "bad-1",
            },
        ]
    )
    state = {"messages": [msg]}
    result = guardrail_node(state)
    assert result["blocked"]
    assert len(result["messages"]) == 1
    assert "SECURITY BLOCK" in result["messages"][0].content


def test_guardrail_blocks_sudo():
    """Test that guardrail blocks sudo commands."""
    msg = MockMessage(
        tool_calls=[
            {
                "name": "run_command",
                "args": {"command": "sudo apt install foo"},
                "id": "bad-2",
            },
        ]
    )
    state = {"messages": [msg]}
    result = guardrail_node(state)
    assert result["blocked"]
    assert "SECURITY BLOCK" in result["messages"][0].content


def test_guardrail_blocks_system_path_writes():
    """Test that guardrail blocks writes to system paths."""
    msg = MockMessage(
        tool_calls=[
            {
                "name": "write_file",
                "args": {"path": "/etc/passwd", "content": "hack"},
                "id": "bad-3",
            },
        ]
    )
    state = {"messages": [msg]}
    result = guardrail_node(state)
    assert result["blocked"]
    assert "system path" in result["messages"][0].content.lower()


def test_guardrail_allows_safe_write():
    """Test that guardrail allows safe file writes."""
    msg = MockMessage(
        tool_calls=[
            {
                "name": "write_file",
                "args": {"path": "./hello.py", "content": "print('hi')"},
                "id": "good-1",
            },
        ]
    )
    state = {"messages": [msg]}
    result = guardrail_node(state)
    assert not result["blocked"]


def test_guardrail_no_tool_calls():
    """Test that guardrail passes through messages without tool calls."""
    msg = MockMessage(tool_calls=None, content="Just some text")
    state = {"messages": [msg]}
    result = guardrail_node(state)
    assert not result["blocked"]
    assert result["messages"] == []


def test_blocked_substrings_present():
    """Test that expected dangerous substrings are in the blocklist."""
    assert " rm " in BLOCKED_CMD_SUBSTR
    assert "sudo" in BLOCKED_CMD_SUBSTR
    assert "mkfs" in BLOCKED_CMD_SUBSTR
    assert "shutdown" in BLOCKED_CMD_SUBSTR


def test_system_paths_present():
    """Test that expected system paths are in the blocklist."""
    assert "/etc" in SYSTEM_PATH_PREFIXES
    assert "/usr" in SYSTEM_PATH_PREFIXES
    assert "/bin" in SYSTEM_PATH_PREFIXES
