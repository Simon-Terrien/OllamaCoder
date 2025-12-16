# Hybrid Agent Overview

## Architecture
- **Supervisor** orchestrates the workflow, delegating tasks and enforcing guardrails.
- **Planner** breaks down user goals into actionable steps and coordinates execution.
- **Coding Squad** focuses on writing and iterating on code changes.
- **Architect** reviews plans and code for design quality and adherence to patterns.
- **DevOps** validates commands, manages tool calls, and ensures changes are ready to apply.

Key entry points:
- `hybrid_agent.py` — interactive CLI agent runner.
- `mcp_server.py` — exposes filesystem and run-command tools for MCP-compatible clients.
- `api` package — FastAPI HTTP interface (`uv run python -m ollama_coder.api`).

## Installation & Running
- Install in editable mode: `uv pip install -e .`
- Run the hybrid agent: `uv run python -m ollama_coder.hybrid_agent --task "Create hello.py and test it"`
- Start the MCP server: `uv run python -m ollama_coder.mcp_server`
- Launch the HTTP API: `uv run python -m ollama_coder.api`

## Configuration
- **Models**: set `CODER_MODEL` and `REVIEWER_MODEL` env vars to override defaults.
- **Validator command**: configure via `VALIDATOR_COMMAND` (defaults to `pytest -q`).
- **Apply changes**: toggle `APPLY_CHANGES` (true/false) to allow writing files.

## Logging
- Runtime events are written to `logs/events.jsonl`; rotate or archive as needed.

## Testing
- Run the suite with `uv run pytest -q`.

## Benchmarks
- Run sample tasks through the agent and log metrics: `uv run python scripts/benchmark.py --coder-model qwen2.5-coder:7b --reviewer-model llama3.2`
- Summarize accumulated runs (JSONL): `scripts/benchmark_summary.sh logs/benchmark_results.jsonl`
