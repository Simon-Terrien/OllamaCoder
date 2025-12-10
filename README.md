# Ollama Coder — Hybrid Multi-Agent System

A self-correcting coding agent system with guardrails powered by **Ollama + LangGraph**.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         SUPERVISOR                               │
│  Routes tasks to specialized agents based on task analysis       │
└─────────────────┬───────────────────────────────────────────────┘
                  │
    ┌─────────────┼─────────────┬─────────────┬─────────────┐
    ▼             ▼             ▼             ▼             ▼
┌────────┐  ┌──────────┐  ┌──────────┐  ┌─────────┐  ┌────────┐
│Planner │  │CodingSquad│  │Architect │  │ DevOps  │  │ FINISH │
│        │  │Coder↔Review│ │ISO-42010 │  │CI/CD    │  │        │
└────────┘  └──────────┘  └──────────┘  └─────────┘  └────────┘
                  │
    ┌─────────────┼─────────────┐
    ▼             ▼             ▼
┌────────┐  ┌──────────┐  ┌─────────┐
│Guardrail│  │  Tools   │  │Validator│
│Security │  │ MCP FS   │  │ pytest  │
└────────┘  └──────────┘  └─────────┘
```

## Features

### Core Features
- **Supervisor** routes coding tasks to specialized agents
- **CodingSquad** (Coder ↔ Reviewer) swarm for code writing and review
- **Architect** agent for ISO-42010 documentation and security posture analysis
- **DevOps** agent for CI/CD, Docker, Kubernetes configurations
- **Planner** agent for task decomposition
- **Guardrail** blocks dangerous commands (rm, sudo, mkfs, system paths)
- **Validator** runs pytest to verify code correctness
- **MCP Server** provides filesystem and run_command tools

### Batch Processing (NEW)
- **Parallel Agent Tasks** - Process thousands of coding tasks concurrently
- **Batch Validation** - Validate multiple files/projects simultaneously
- **Batch Testing** - Run tests across multiple modules in parallel
- **Bulk MCP Operations** - Perform filesystem operations at scale
- **Dual Backend** - SQLite (simple) or Celery (distributed/production)
- **Job Queue System** - SQLite-backed async queue with progress tracking
- **Celery Integration** - Production-grade distributed processing with Redis/RabbitMQ
- **RESTful API** - Submit and monitor batch jobs via HTTP

## Quickstart

### 1. Prerequisites

- Python 3.11+
- [Ollama](https://ollama.ai) installed and running
- Pull required models:

```bash
ollama pull qwen2.5-coder:7b
ollama pull llama3.2
```

### 2. Install

```bash
# Clone or extract the project
cd ollama-coder

# Install with uv (recommended)
uv pip install -e .

# Or with pip
pip install -e .
```

### 3. Run the Agent

```bash
# Interactive mode
uv run python -m ollama_coder.hybrid_agent

# With a task
uv run python -m ollama_coder.hybrid_agent --task "Create a hello.py file that prints Hello World"

# With custom models
uv run python -m ollama_coder.hybrid_agent \
  --task "Add tests for my code" \
  --coder-model qwen2.5-coder:14b \
  --reviewer-model llama3.2:3b
```

### 4. Run the API Server

```bash
uv run python -m ollama_coder.api
# Then open http://127.0.0.1:8000/docs
```

## CLI Options

| Flag | Default | Description |
|------|---------|-------------|
| `--task` | (interactive) | Task description |
| `--check-command` | `pytest -q` | Validator command (empty to disable) |
| `--max-loops` | `16` | Maximum agent iteration loops |
| `--recursion-limit` | `80` | LangGraph recursion limit |
| `--coder-model` | `qwen2.5-coder:7b` | Ollama model for coder |
| `--reviewer-model` | `llama3.2` | Ollama model for reviewer |

## API Endpoints

### Core Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check with available tools |
| `/run` | POST | One-shot agent execution |
| `/sessions` | POST | Create a persistent session |
| `/sessions/{id}/run` | POST | Run task in session |
| `/pydantic/run` | POST | Run Pydantic-AI orchestrator |

### Batch Processing Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/batch/agent-tasks` | POST | Submit multiple coding tasks for batch processing |
| `/batch/validation` | POST | Validate multiple files/projects in parallel |
| `/batch/tests` | POST | Execute tests across multiple modules |
| `/batch/mcp-operations` | POST | Perform bulk filesystem operations |
| `/batch/jobs/{id}` | GET | Get job status and results |
| `/batch/jobs` | GET | List jobs with filtering |
| `/batch/jobs/{id}` | DELETE | Cancel a job |
| `/batch/stats` | GET | Get queue statistics |

## Batch Processing Quick Example

Process 100 coding tasks in parallel:

```bash
curl -X POST http://127.0.0.1:8000/batch/agent-tasks \
  -H "Content-Type: application/json" \
  -d '{
    "tasks": [
      {"id": "task1", "description": "Create hello.py with Hello World"},
      {"id": "task2", "description": "Add unit tests for hello.py"},
      ...
    ],
    "parallel": 5
  }'
```

Check progress:

```bash
curl http://127.0.0.1:8000/batch/jobs/{job_id}
```

See [docs/BATCH_PROCESSING.md](docs/BATCH_PROCESSING.md) for complete guide.

## Project Structure

```
ollama-coder/
├── src/ollama_coder/
│   ├── __init__.py
│   ├── hybrid_agent.py      # Main entry point
│   ├── api.py               # FastAPI server (with batch endpoints)
│   ├── mcp_server.py        # MCP filesystem tools
│   ├── core/
│   │   ├── config.py        # RunConfig dataclass
│   │   ├── supervisor.py    # Main graph builder
│   │   ├── squad.py         # Coder/Reviewer swarm
│   │   ├── architect.py     # Architecture documentation
│   │   ├── devops.py        # CI/CD agent
│   │   ├── planner.py       # Task planning
│   │   ├── guardrail.py     # Security guardrails
│   │   ├── validator.py     # Code validation
│   │   └── mcp_loader.py    # MCP client loader
│   ├── batch/               # Batch processing (NEW)
│   │   ├── __init__.py
│   │   ├── job_queue.py     # Async job queue with SQLite
│   │   ├── processors.py    # Batch processors
│   │   └── progress.py      # Progress tracking
│   └── pydantic_agents/     # Pydantic-AI agents (alternative)
│       ├── models.py        # Data models
│       ├── orchestrator.py  # Main orchestrator
│       ├── planner_agent.py
│       ├── coding_agent.py
│       ├── security_agent.py
│       ├── docs_agent.py
│       └── tools.py
├── tests/
│   ├── test_config.py
│   ├── test_guardrail.py
│   └── test_batch_processing.py  # Batch tests (NEW)
├── docs/
│   └── BATCH_PROCESSING.md  # Batch guide (NEW)
├── data/                    # Created at runtime
│   └── batch_jobs.db        # Job queue database
├── pyproject.toml
├── pytest.ini
└── README.md
```

## Security Guardrails

The guardrail blocks:
- Commands: `rm`, `sudo`, `mkfs`, `shutdown`, `reboot`
- Writes to: `/etc`, `/usr`, `/bin`, `/sbin`, `/lib`

## Validator Behavior

- Runs `pytest -q` by default
- Exit code 0 = success
- Exit code 5 (no tests) = soft pass
- Any other exit = retry with different agent

## Recommended Models

| Use Case | Model | Notes |
|----------|-------|-------|
| **Coding** | `qwen2.5-coder:7b` | Fast, good code generation |
| **Coding (quality)** | `qwen2.5-coder:14b` | Better quality, slower |
| **Review** | `llama3.2` | Good at reasoning |
| **Architecture** | `qwen3:8b` | Good at documentation |

For computer use / GUI automation, consider:
- **Fara-7B** (Microsoft) - Specialized for browser automation
- **qwen3-vl** - Vision-language model for screenshots

## Logs

Runtime logs are stored in `logs/events.jsonl` (created at runtime).

## Testing

```bash
# Install dev deps (adds pytest + pytest-asyncio)
uv pip install -e ".[dev]"

# Run tests
uv run pytest -q   # or: .venv/bin/pytest -q

# Run with verbose output
uv run pytest -v
```

## Pre-commit & CI

```bash
# Install hook tooling
uv pip install pre-commit

# Set up git hooks
pre-commit install

# Run all hooks (ruff) on demand
pre-commit run --all-files
```

CI:
- `.github/workflows/pre-commit.yml` runs ruff on pushes/PRs (with caching).
- `.github/workflows/test.yml` runs `uv run pytest -q` with dev extras on pushes/PRs.

## Development

```bash
# Install dev dependencies
uv pip install -e ".[dev]"

# Format code
ruff format src tests

# Lint
ruff check src tests
```

## License

MIT
