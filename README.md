# Ollama Coder

Multi‑agent coding system for Ollama/LangGraph with guardrails, a FastAPI surface, batch processing, and an OpenAI-style chat facade.

## What it does
- Supervisor graph routes work to Coder/Reviewer squad, Architect, DevOps, and Planner agents.
- Guardrail blocks destructive shells; Validator runs `pytest -q` by default.
- HTTP API exposes one-shot runs, long-lived sessions, batch queues, and `/v1/chat/completions` compatibility.
- MCP server offers filesystem + `run_command` tools; batch processors can drive MCP operations at scale.
- Includes Pydantic-AI orchestrator endpoint for type-safe automation.

## Install & run
- Install deps (editable): `uv pip install -e .` (or `pip install -e .`).
- Hybrid agent REPL: `uv run python -m ollama_coder.hybrid_agent --task "Create hello.py"`.
- API server: `uv run python -m ollama_coder.api` then open http://127.0.0.1:8000/docs.
- Standalone MCP server: `uv run python -m ollama_coder.mcp_server`.
- Console entrypoints (from `pyproject.toml`): `ollama-coder`, `ollama-coder-api`, `ollama-mcp-server`, `iso42010_analyzer`.
- ISO 42010 snapshot: `uv run iso42010_analyzer --root . --format markdown`.

## API highlights (FastAPI)
- `GET /health` – MCP/tool check.
- `POST /run` – single task via supervisor.
- Sessions: `POST /sessions`, `POST /sessions/{id}/run`, `GET /sessions/{id}`.
- Pydantic orchestrator: `POST /pydantic/run` for type-safe workflows.
- OpenAI facade: `POST /v1/chat/completions` (uses supervisor graph/models).
- Batch queue: `POST /batch/agent-tasks`, `/batch/validation`, `/batch/tests`, `/batch/mcp-operations`; status via `/batch/jobs` + `/batch/stats`; cancellation via `DELETE /batch/jobs/{id}`.

## Project layout
- Core agents & config: `src/ollama_coder/core/`
- API surface: `src/ollama_coder/api.py`
- Batch queue + processors: `src/ollama_coder/batch/`
- MCP server/tools: `src/ollama_coder/mcp_server.py`
- Tools: `src/ollama_coder/tools/` (e.g., `iso42010_analyzer`)
- Pydantic orchestrator: `src/ollama_coder/pydantic_agents/`
- Tests: `tests/` (e.g., `tests/test_batch_processing.py`, `tests/test_hello.py`)

## Testing
- Run all tests: `uv run pytest -q`
- Example single test: `uv run pytest tests/test_hello.py -q`
- Validator uses the same command; adjust via `RunConfig.check_command` or API payload.

## Notes
- Logs stream to `logs/events.jsonl` at runtime.
- Default models: coder `qwen2.5-coder:7b`, reviewer `llama3.2`; override per request.
