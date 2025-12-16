# Repository Guidelines

## Project Structure & Module Organization
- Core code lives in `src/ollama_coder/`. Key pieces: `hybrid_agent.py` (entrypoint), `core/` (supervisor, planner, guardrail, validator, config), `mcp_server.py` (filesystem/run-command tools), and `pydantic_agents/` (type-safe agent helpers).
- Tests sit in `tests/`; add new suites as `test_*.py`. Runtime logs default to `logs/events.jsonl` (created at run time).
- Executable console scripts are defined via `pyproject.toml` under `[project.scripts]` (e.g., `ollama-coder`, `ollama-mcp-server`, `ollama-coder-api`).
- Quick reference for commands/endpoints lives in `USAGE_CHEATSHEET.md` (keep it current when flows change).

## Build, Test, and Development Commands
- Install deps (editable): `uv pip install -e .` (or `pip install -e .` if `uv` is unavailable).
- Run hybrid agent: `uv run python -m ollama_coder.hybrid_agent --task "Create hello.py and test it"`.
- Start MCP server (tools + FS): `uv run python -m ollama_coder.mcp_server`.
- Launch HTTP API (FastAPI): `uv run python -m ollama_coder.api`.
- Tests: `uv run pytest -q` (validator also defaults to this command when the agent self-checks).

## Coding Style & Naming Conventions
- Python 3.11+, 4-space indentation, prefer type hints (`from __future__ import annotations` already used in core files).
- Modules, files, functions, and variables use `snake_case`; classes use `PascalCase`; constants `UPPER_SNAKE`.
- Keep agent behaviors deterministic and side-effect safe; guardrail rules live in `core/guardrail.py`—adjust deliberately and document changes.

## Testing Guidelines
- Use `pytest`; name files `test_*.py` and functions `test_*`.
- Add focused unit tests alongside the feature area; include one positive and one failure/guardrail case when touching `core/` logic.
- If the validator command changes, mirror that in docs and ensure CI (when present) still runs `pytest -q`.
- Repository sanity check: `tests/test_hello.py` asserts `hello.py` prints exactly `Hello` (stdout stripped), so preserve that behaviour when modifying the sample script.

## Commit & Pull Request Guidelines
- Commit messages: short imperative summary (e.g., "Add guardrail for sudo"); keep subject ≤72 chars.
- PRs should link an issue or clearly state scope, list test command(s) run, and include any relevant agent task transcript snippets from `logs/events.jsonl`.
- Include configuration notes when changing defaults (models, recursion limits, validator command) so operators can reproduce runs.

## Security & Configuration Tips
- Guardrail blocks destructive shells (e.g., `rm`, `sudo`, writes to `/etc`); do not bypass unless explicitly required and documented.
- Store secrets outside the repo; the MCP server exposes filesystem/run_command—scope it cautiously when deploying.
