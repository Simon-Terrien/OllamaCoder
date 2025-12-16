import os
import subprocess
from pathlib import Path

from mcp.server.fastmcp import FastMCP

# Default sandbox root for MCP tools; keeps generated artifacts out of repo root.
BASE_DIR = Path(
    os.environ.get("OLLAMA_CODER_PROJECT_ROOT", Path(__file__).resolve().parents[2] / "project")
).resolve()
BASE_DIR.mkdir(parents=True, exist_ok=True)

mcp = FastMCP("filesystem")


def _resolve(path: str) -> Path:
    """Resolve a user path to a safe location inside BASE_DIR."""
    raw = Path(path)
    if raw.is_absolute():
        # Allow absolute paths already under BASE_DIR; otherwise remap under BASE_DIR.
        if str(raw).startswith(str(BASE_DIR)):
            candidate = raw
        else:
            candidate = BASE_DIR / raw.relative_to("/")
    else:
        candidate = BASE_DIR / raw
    resolved = candidate.resolve()
    if not str(resolved).startswith(str(BASE_DIR)):
        raise PermissionError(f"Path {path} escapes sandbox root {BASE_DIR}")
    return resolved


@mcp.tool()
def list_files(path: str = ".") -> str:
    try:
        target = _resolve(path)
        return "\n".join(os.listdir(target))
    except Exception as e:  # noqa: BLE001
        return str(e)


@mcp.tool()
def read_file(path: str) -> str:
    try:
        target = _resolve(path)
    except Exception as e:  # noqa: BLE001
        return str(e)
    if not target.exists():
        return "File not found."
    with open(target, "r", encoding="utf-8") as f:
        return f.read()


@mcp.tool()
def write_file(path: str, content: str) -> str:
    try:
        target = _resolve(path)
    except Exception as e:  # noqa: BLE001
        return str(e)
    target.parent.mkdir(parents=True, exist_ok=True)
    with open(target, "w", encoding="utf-8") as f:
        f.write(content)
    return f"Wrote to {target}"


@mcp.tool()
def run_command(command: str, cwd: str = ".") -> str:
    try:
        workdir = _resolve(cwd)
    except Exception as e:  # noqa: BLE001
        return f"Error: {e}"
    try:
        proc = subprocess.run(
            command,
            shell=True,
            cwd=workdir,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if proc.returncode == 0:
            return f"STDOUT\n{proc.stdout}"
        return f"STDERR\n{proc.stderr}"
    except subprocess.TimeoutExpired:
        return "Error: Command timed out."
    except Exception as e:  # noqa: BLE001
        return f"Error: {e}"


@mcp.tool()
def sandbox_root() -> str:
    """Return the active sandbox root for MCP file operations."""
    return str(BASE_DIR)


def main():
    """Run MCP filesystem server over stdio."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
