import os
import subprocess

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("filesystem")


@mcp.tool()
def list_files(path: str = ".") -> str:
    try:
        return "\n".join(os.listdir(path))
    except Exception as e:  # noqa: BLE001
        return str(e)


@mcp.tool()
def read_file(path: str) -> str:
    if not os.path.exists(path):
        return "File not found."
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


@mcp.tool()
def write_file(path: str, content: str) -> str:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return f"Wrote to {path}"


@mcp.tool()
def run_command(command: str, cwd: str = ".") -> str:
    try:
        proc = subprocess.run(
            command,
            shell=True,
            cwd=cwd,
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


def main():
    """Run MCP filesystem server over stdio."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
