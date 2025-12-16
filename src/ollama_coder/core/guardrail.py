from __future__ import annotations

from typing import List

from langchain_core.messages import ToolMessage

BLOCKED_CMD_SUBSTR = [
    " rm ",
    " rm-",
    " rm -rf",
    "sudo",
    "mkfs",
    "shutdown",
    "reboot",
    "> /dev/sd",
    ";rm ",
    "&&rm ",
    "| rm ",
]
BLOCKED_CMD_PREFIXES = ["rm ", "rm-"]
SYSTEM_PATH_PREFIXES = ("/etc", "/usr", "/bin", "/sbin", "/lib")


def _apply_changes_enabled(state) -> bool:
    cfg = state.get("config") if isinstance(state, dict) else None
    if cfg is None:
        return True
    return getattr(cfg, "apply_changes", True)


def guardrail_node(state):
    last = state["messages"][-1]
    if not hasattr(last, "tool_calls") or not last.tool_calls:
        return {"blocked": False, "messages": []}

    rejections: List[ToolMessage] = []
    apply_changes = _apply_changes_enabled(state)

    for call in last.tool_calls:
        name = call.get("name", "")
        args = call.get("args", {}) if isinstance(call, dict) else getattr(call, "args", {})

        if not apply_changes and name in {"write_file", "run_command"}:
            action = "write_file" if name == "write_file" else "run_command"
            target = args.get("path") or args.get("command") or ""
            rejections.append(
                ToolMessage(
                    tool_call_id=call["id"],
                    content=(
                        "READ-ONLY MODE: apply_changes is False, "
                        f"so {action}('{target}') is blocked."
                    ),
                )
            )
            continue

        if name == "run_command":
            cmd = str(args.get("command", ""))
            low = cmd.lower()
            if any(sub in low for sub in BLOCKED_CMD_SUBSTR) or any(
                low.startswith(prefix) for prefix in BLOCKED_CMD_PREFIXES
            ):
                rejections.append(
                    ToolMessage(
                        tool_call_id=call["id"],
                        content=f"SECURITY BLOCK: command '{cmd}' is not allowed.",
                    )
                )
                continue

        if name == "write_file":
            path = str(args.get("path", ""))
            if path.startswith(SYSTEM_PATH_PREFIXES):
                rejections.append(
                    ToolMessage(
                        tool_call_id=call["id"],
                        content=f"SECURITY BLOCK: writing to system path '{path}' denied.",
                    )
                )
                continue

    if rejections:
        return {"messages": rejections, "blocked": True}

    return {"blocked": False, "messages": []}
