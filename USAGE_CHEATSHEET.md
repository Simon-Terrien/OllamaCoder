# Ollama Coder – Usage Cheat Sheet

## Install & Setup
- Editable install: `uv pip install -e .` (or `pip install -e .`).
- Optional dev extras: `uv pip install -e ".[dev]"`.
- Logs appear at `logs/events.jsonl` when running agents/API.

## Quick Runs
- Interactive hybrid agent: `uv run python -m ollama_coder.hybrid_agent`.
- One-shot task: `uv run python -m ollama_coder.hybrid_agent --task "Create hello.py"`.
- Change models: `--coder-model qwen2.5-coder:14b --reviewer-model llama3.2`.

## API (FastAPI)
- Start server: `uv run python -m ollama_coder.api` → docs at http://127.0.0.1:8000/docs.
- Health: `GET /health`.
- One-shot run: `POST /run` with body `{ "task": "...", "check_command": "pytest -q" }`.
- Sessions: `POST /sessions` → `POST /sessions/{id}/run` → `GET /sessions/{id}`.
- OpenAI-compatible: `POST /v1/chat/completions` with `messages` array; defaults to supervisor graph.
- Pydantic orchestrator: `POST /pydantic/run` with `task`, `project_root`, `apply_changes`.

## Batch Queue
- Endpoints: `POST /batch/agent-tasks`, `/batch/validation`, `/batch/tests`, `/batch/mcp-operations`.
- Job status: `GET /batch/jobs/{job_id}`; list: `GET /batch/jobs`; stats: `GET /batch/stats`; cancel: `DELETE /batch/jobs/{job_id}`.
- Typical payload snippet:
  - Agent tasks: `{ "tasks": [{"id": "t1", "description": "..." }], "chunk_size": 10, "parallel": 3 }`.
  - Validation: `{ "targets": [{"id": "f1", "path": "src/..."}], "check_command": "pytest -q" }`.

## MCP Server
- Start tools server: `uv run python -m ollama_coder.mcp_server`.
- Provides filesystem (`read_file`, `write_file`, `list_directory`) and `run_command` tools with guardrails.

## Config Knobs (RunConfig)
- `check_command` (default `"pytest -q"`; set to `null` to disable validator).
- `max_loops` default 16; `recursion_limit` default 80.
- `coder_model` default `qwen2.5-coder:7b`; `reviewer_model` default `llama3.2`.

## Testing
- All tests: `uv run pytest -q` (validator uses same command).
- Single file: `uv run pytest tests/test_batch_processing.py -v`.
- Example hello test: `uv run pytest tests/test_hello.py -q`.

## Guardrail Highlights
- Blocks destructive shells (`rm`, `sudo`, system paths like `/etc`).
- Failing validator or guardrail sets `blocked`/`validator_ok` flags in graph state.

## Examples (curl)
- Run task once:
  - `curl -X POST http://127.0.0.1:8000/run -H "Content-Type: application/json" -d '{\"task\":\"Add tests\",\"check_command\":\"pytest -q\"}'`
- Chat completion:
  - `curl -X POST http://127.0.0.1:8000/v1/chat/completions -H \"Content-Type: application/json\" -d '{\"messages\":[{\"role\":\"user\",\"content\":\"Write fizzbuzz\"}]}'`
- Batch status:
  - `curl http://127.0.0.1:8000/batch/jobs`

## When to Use What
- Need iterative coding with validation → `/run` or `/sessions`.
- Need OpenAI-compatible drop-in → `/v1/chat/completions`.
- Need many tasks/files/tests at once → batch endpoints.
- Need filesystem/command tooling for another client → `mcp_server`.

## ISO 42010 snapshot
- Generate architecture summary: `uv run iso42010_analyzer --root . --format markdown` (or `json`).
