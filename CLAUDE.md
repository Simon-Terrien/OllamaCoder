# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Ollama Coder is a self-correcting multi-agent coding system with security guardrails powered by Ollama + LangGraph. The system uses a Supervisor agent to route tasks to specialized agents (Planner, CodingSquad, Architect, DevOps) that collaborate through LangGraph state machines.

**NEW**: Includes batch processing capabilities for parallel execution of thousands of operations including agent tasks, code validation, test execution, and MCP operations.

## Core Architecture

### Multi-Agent System Flow
1. **Supervisor** (`core/supervisor.py`) - Main orchestrator that routes tasks to specialized agents based on request analysis
2. **CodingSquad** (`core/squad.py`) - A swarm of Coder ↔ Reviewer agents that collaborate iteratively on code
3. **Architect** (`core/architect.py`) - Handles ISO-42010 architecture documentation and security posture analysis
4. **DevOps** (`core/devops.py`) - Manages CI/CD, Docker, Kubernetes, and infrastructure-as-code tasks
5. **Planner** (`core/planner.py`) - Breaks down complex tasks into step-by-step plans

### State Management
- All agents share state through LangGraph's `StateGraph` with typed dictionaries
- State includes: messages, active_agent, loop_count, validator_ok, blocked, config, plan, step_index
- State flows: START → Supervisor → (Agent) → Supervisor → ... → END

### Security Layer
- **Guardrail** (`core/guardrail.py`) - Intercepts and blocks dangerous tool calls before execution
  - Blocked commands: `rm`, `sudo`, `mkfs`, `shutdown`, `reboot`, shell injections
  - Blocked write paths: `/etc`, `/usr`, `/bin`, `/sbin`, `/lib`
  - Returns SECURITY BLOCK messages to agents when violations detected
- **Validator** (`core/validator.py`) - Runs `pytest -q` (configurable) to verify code correctness
  - Exit code 0 = success, 5 (no tests) = soft pass, others = retry

### Tool Integration
- **MCP Server** (`mcp_server.py`) - Provides filesystem (`read_file`, `write_file`, `list_directory`) and `run_command` tools
- **MCP Loader** (`core/mcp_loader.py`) - Async loader that connects to MCP server and adapts tools for LangChain

### Configuration
- `RunConfig` dataclass (`core/config.py`) controls all runtime behavior:
  - `check_command`: Validator command (default: `"pytest -q"`, set to `None` to disable)
  - `max_loops`: Maximum agent iterations (default: 16)
  - `recursion_limit`: LangGraph recursion depth (default: 80)
  - `coder_model`: Ollama model for Coder agent (default: `"qwen2.5-coder:7b"`)
  - `reviewer_model`: Ollama model for Reviewer agent (default: `"llama3.2"`)

## Common Development Commands

### Running the Agent
```bash
# Interactive mode
uv run python -m ollama_coder.hybrid_agent

# With a specific task
uv run python -m ollama_coder.hybrid_agent --task "Create a hello.py file that prints Hello World"

# With custom models and configuration
uv run python -m ollama_coder.hybrid_agent \
  --task "Add tests for my code" \
  --coder-model qwen2.5-coder:14b \
  --reviewer-model llama3.2:3b \
  --max-loops 20
```

### Testing
```bash
# Run all tests (this is what the validator uses)
uv run pytest -q

# Run tests with verbose output
uv run pytest -v

# Run a single test file
uv run pytest tests/test_guardrail.py -v

# Run a specific test function
uv run pytest tests/test_guardrail.py::test_guardrail_blocks_rm -v
```

### Sanity check
- `tests/test_hello.py` expects running `python hello.py` from repo root prints `Hello` (stdout stripped) with no stderr; keep `hello.py` aligned to avoid baseline failure.

### API Server
```bash
# Start FastAPI server
uv run python -m ollama_coder.api

# Access API docs at http://127.0.0.1:8000/docs
```

### MCP Server (Standalone)
```bash
# Run MCP server directly
uv run python -m ollama_coder.mcp_server
```

### Installation
```bash
# Install with uv (recommended)
uv pip install -e .

# Install with pip
pip install -e .

# Install with dev dependencies (for linting)
uv pip install -e ".[dev]"
```

## Important Implementation Details

### Agent Communication Pattern
- Agents use `transfer_to_X` tool calls to switch control (e.g., `transfer_to_reviewer`)
- The CodingSquad implements a two-agent swarm: Coder writes code, Reviewer critiques it
- Loop terminates when: (1) validator passes, (2) max_loops reached, or (3) security block occurs

### Supervisor Routing Logic
The Supervisor uses an LLM to decide routing based on these rules:
- Architecture/ISO-42010/security posture → Architect
- CI/CD/Docker/Kubernetes/infra-as-code → DevOps
- Coding/tests on application code → CodingSquad
- Planning/task breakdown → Planner
- If plan exists, dispatch steps sequentially mapping: devops→DevOps, security→Architect, docs→Architect, tests/backend/frontend→CodingSquad
- Otherwise → FINISH

### Validator Exit Code Handling
The validator interprets pytest exit codes:
- 0 = All tests passed (validator_ok=True)
- 5 = No tests collected (soft pass, validator_ok=True)
- Any other = Tests failed (validator_ok=False, retry with different agent)

### Tool Call Extraction
- Agents may return JSON tool calls in markdown code blocks or plain JSON
- `_extract_tool_calls()` in `squad.py` handles best-effort parsing and cleaning
- Synthetic tool call IDs are generated for tracking

## Testing Guidelines

- All test files must be in `tests/` directory and named `test_*.py`
- Test functions must be named `test_*`
- pytest.ini configures: `-v --tb=short` with deprecation warnings ignored
- When adding guardrail rules, add corresponding tests to `tests/test_guardrail.py`
- When modifying agent behavior, ensure existing tests still pass

## Logging

Runtime agent events are logged to `logs/events.jsonl` (auto-created at runtime). This includes:
- Agent transitions
- Tool calls and results
- Validation outcomes
- Security blocks

## Model Recommendations

Based on README.md guidance:
- **Fast coding**: `qwen2.5-coder:7b` (default)
- **Quality coding**: `qwen2.5-coder:14b`
- **Code review**: `llama3.2` (default)
- **Architecture docs**: `qwen3:8b`

## Security Constraints

When working with this codebase:
- NEVER bypass guardrail checks without explicit documentation and justification
- NEVER add tools that could expose system-level access without guardrail protection
- Test all new MCP tools against guardrail rules
- Document any changes to `BLOCKED_CMD_SUBSTR`, `BLOCKED_CMD_PREFIXES`, or `SYSTEM_PATH_PREFIXES`

## Batch Processing System

### Architecture
- **JobQueue** (`batch/job_queue.py`) - SQLite-backed async job queue with worker pool
- **Processors** (`batch/processors.py`) - Specialized processors for each operation type:
  - `BatchAgentProcessor` - Process multiple coding tasks in parallel
  - `BatchValidationProcessor` - Validate multiple files/projects
  - `BatchTestProcessor` - Execute tests across modules
  - `BatchMCPProcessor` - Bulk filesystem operations
- **ProgressTracker** (`batch/progress.py`) - Real-time progress metrics

### API Endpoints
All batch endpoints are in `api.py`:
- `POST /batch/agent-tasks` - Submit coding tasks for batch processing
- `POST /batch/validation` - Batch validation
- `POST /batch/tests` - Batch test execution
- `POST /batch/mcp-operations` - Bulk MCP operations
- `GET /batch/jobs/{job_id}` - Get job status
- `GET /batch/jobs` - List jobs
- `DELETE /batch/jobs/{job_id}` - Cancel job
- `GET /batch/stats` - Queue statistics
- `POST /pydantic/run` - Type-safe orchestration via Pydantic-AI
- `POST /v1/chat/completions` - OpenAI-compatible supervisor facade

### Key Concepts
- Jobs are persisted in SQLite at `data/batch_jobs.db`
- Worker pool processes jobs asynchronously (default: 5 workers)
- Jobs have statuses: queued, running, completed, failed, cancelled
- Progress tracking includes: percentage, items/sec, estimated time remaining
- Processors use semaphores to limit concurrent operations

### Testing Batch Processing
```bash
# Run batch processing tests
uv run pytest tests/test_batch_processing.py -v

# Test specific processor
uv run pytest tests/test_batch_processing.py::test_batch_validation_processor -v
```

## Quick reference
- Concise commands/endpoints live in `USAGE_CHEATSHEET.md`; update alongside code/API changes.

### Common Batch Operations
```bash
# Submit batch agent tasks via API
curl -X POST http://127.0.0.1:8000/batch/agent-tasks \
  -H "Content-Type: application/json" \
  -d '{"tasks": [{"id": "task1", "description": "Create hello.py"}], "parallel": 3}'

# Check job status
curl http://127.0.0.1:8000/batch/jobs/{job_id}
```

See `docs/BATCH_PROCESSING.md` for comprehensive guide.

## Alternative Implementation

The `pydantic_agents/` directory contains a Pydantic-AI based alternative implementation with:
- `orchestrator.py` - Main Pydantic-AI orchestrator
- `planner_agent.py`, `coding_agent.py`, `security_agent.py`, `docs_agent.py` - Specialized agents
- This is separate from the main LangGraph implementation in `core/`
