from __future__ import annotations

import subprocess

from langchain_core.messages import ToolMessage

from .config import RunConfig


def validator_node(state):
    cfg: RunConfig = state["config"]
    if not cfg.check_command:
        return {"messages": [], "validator_ok": True}

    try:
        proc = subprocess.run(
            cfg.check_command,
            shell=True,
            text=True,
            capture_output=True,
            timeout=60,
        )
    except subprocess.TimeoutExpired:
        content = "VALIDATOR TIMEOUT"
        ok = False
    except Exception as exc:  # noqa: BLE001
        content = f"VALIDATOR ERROR: {exc}"
        ok = False
    else:
        content = f"VALIDATOR STDOUT\n{proc.stdout}\nVALIDATOR STDERR\n{proc.stderr}\nEXIT {proc.returncode}"
        ok = proc.returncode == 0 or (
            proc.returncode == 5
            and ("no tests ran" in proc.stdout.lower() or "no tests collected" in proc.stdout.lower())
        )

    return {
        "messages": [ToolMessage(tool_call_id="validator", content=content)],
        "validator_ok": ok,
    }
