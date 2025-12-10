from __future__ import annotations
import sys
import asyncio

from langchain_mcp_adapters.client import MultiServerMCPClient

_client: MultiServerMCPClient | None = None
_tools = None


async def get_mcp_tools():
    """Return cached LangChain tools from MCP server."""
    global _tools, _client
    if _tools is not None:
        return _tools

    _client = MultiServerMCPClient(
        {
            "filesystem": {
                "command": sys.executable,
                "args": ["-m", "ollama_coder.mcp_server"],
                "transport": "stdio",
            }
        }
    )

    # MultiServerMCPClient is not an async context manager; just fetch tools.
    _tools = await _client.get_tools()
    return _tools


async def close_mcp_session():
    """No-op placeholder kept for API symmetry."""
    return None
