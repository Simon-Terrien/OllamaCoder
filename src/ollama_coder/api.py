"""HTTP API for running the hybrid agent (Coder/Architect/DevOps) in tests.

Endpoints (high level):
- GET  /health                 : basic MCP + agent health check.
- POST /run                    : one-shot run via Supervisor (no session).
- POST /sessions               : create a long-lived agent session.
- POST /sessions/{id}/run      : send a message/task into a specific session.
- GET  /sessions/{id}          : inspect session state.

Run:
  uv run ollama-coder-api
Then open http://127.0.0.1:8000/docs
"""

from __future__ import annotations

import time
import uuid
from typing import Any, Dict, List, Literal, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

# Batch processing
from .batch import (
    BatchAgentProcessor,
    BatchMCPProcessor,
    BatchTestProcessor,
    BatchValidationProcessor,
    JobQueue,
    JobStatus,
)
from .core.architect import create_architect
from .core.config import RunConfig
from .core.devops import create_devops
from .core.mcp_loader import get_mcp_tools
from .core.squad import create_squad
from .core.supervisor import build_graph

# Pydantic-AI orchestrator stack
from .pydantic_agents.orchestrator import OrchestratorDeps, orchestrator_agent

app = FastAPI(title="Ollama Coder API", version="0.2.0")

# Global batch queue instance
batch_queue: Optional[JobQueue] = None


class RunRequest(BaseModel):
    task: str
    check_command: str | None = "pytest -q"
    max_loops: int = 16
    recursion_limit: int = 80
    coder_model: str = "qwen2.5-coder:7b"
    reviewer_model: str = "llama3.2"


class RunResponse(BaseModel):
    status: str
    messages: List[str]


class CreateSessionRequest(BaseModel):
    mode: Literal["supervisor", "coder", "architect", "devops"] = "supervisor"
    check_command: str | None = "pytest -q"
    max_loops: int = 16
    recursion_limit: int = 80
    coder_model: str = "qwen2.5-coder:7b"
    reviewer_model: str = "llama3.2"


class SessionInfo(BaseModel):
    id: str
    mode: str
    check_command: str | None
    max_loops: int
    recursion_limit: int
    coder_model: str
    reviewer_model: str


class SessionRunRequest(BaseModel):
    message: str


class SessionRunResponse(BaseModel):
    status: str
    messages: List[str]


# Pydantic orchestrator request/response
class PydOrchRequest(BaseModel):
    task: str
    project_root: str = "."
    apply_changes: bool = True


class PydOrchResponse(BaseModel):
    status: str
    summary: dict


# OpenAI-compatible Chat Completions
class OpenAIMessage(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str


class ChatCompletionRequest(BaseModel):
    model: str | None = None
    messages: List[OpenAIMessage]
    max_loops: int = 8
    recursion_limit: int = 80
    check_command: str | None = "pytest -q"
    coder_model: str | None = None
    reviewer_model: str | None = None


class ChatCompletionChoice(BaseModel):
    index: int
    message: OpenAIMessage
    finish_reason: str = "stop"


class ChatCompletionUsage(BaseModel):
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    total_tokens: Optional[int] = None


class ChatCompletionResponse(BaseModel):
    id: str
    object: Literal["chat.completion"]
    created: int
    model: str
    choices: List[ChatCompletionChoice]
    usage: Optional[ChatCompletionUsage] = None


class _AgentSession:
    def __init__(self, id: str, mode: str, cfg: RunConfig, app):
        self.id = id
        self.mode = mode
        self.cfg = cfg
        self.app = app
        self.messages: List[tuple[str, str]] = []


SESSIONS: Dict[str, _AgentSession] = {}


@app.get("/health")
async def health():
    tools = await get_mcp_tools()
    tool_names = sorted(t.name for t in tools)
    return {"status": "ok", "tools": tool_names}


@app.post("/run", response_model=RunResponse)
async def run_agent(req: RunRequest):
    cfg = RunConfig(
        check_command=req.check_command or None,
        max_loops=req.max_loops,
        recursion_limit=req.recursion_limit,
        coder_model=req.coder_model,
        reviewer_model=req.reviewer_model,
    )

    graph = await build_graph(cfg)

    initial_state = {
        "messages": [("user", req.task)],
        "active_agent": "Coder",
        "loop_count": 0,
        "validator_ok": False,
        "blocked": False,
        "config": cfg,
    }

    final_state = await graph.ainvoke(initial_state, config={"recursion_limit": cfg.recursion_limit})

    msgs: List[str] = []
    for m in final_state.get("messages", []):
        content = getattr(m, "content", None)
        if content:
            msgs.append(str(content))

    return RunResponse(status="ok", messages=msgs)


@app.post("/sessions", response_model=SessionInfo)
async def create_session(req: CreateSessionRequest):
    cfg = RunConfig(
        check_command=req.check_command or None,
        max_loops=req.max_loops,
        recursion_limit=req.recursion_limit,
        coder_model=req.coder_model,
        reviewer_model=req.reviewer_model,
    )

    tools = await get_mcp_tools()
    mode = req.mode

    if mode == "supervisor":
        app_graph = await build_graph(cfg)
    elif mode == "coder":
        app_graph = create_squad(tools, cfg)
    elif mode == "architect":
        app_graph = create_architect(tools, cfg)
    elif mode == "devops":
        app_graph = create_devops(tools, cfg)
    else:
        raise HTTPException(status_code=400, detail="Unknown mode")

    sid = uuid.uuid4().hex[:8]
    SESSIONS[sid] = _AgentSession(sid, mode, cfg, app_graph)

    return SessionInfo(
        id=sid,
        mode=mode,
        check_command=cfg.check_command,
        max_loops=cfg.max_loops,
        recursion_limit=cfg.recursion_limit,
        coder_model=cfg.coder_model,
        reviewer_model=cfg.reviewer_model,
    )


@app.get("/sessions/{session_id}", response_model=SessionInfo)
async def get_session(session_id: str):
    session = SESSIONS.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    cfg = session.cfg
    return SessionInfo(
        id=session.id,
        mode=session.mode,
        check_command=cfg.check_command,
        max_loops=cfg.max_loops,
        recursion_limit=cfg.recursion_limit,
        coder_model=cfg.coder_model,
        reviewer_model=cfg.reviewer_model,
    )


@app.post("/sessions/{session_id}/run", response_model=SessionRunResponse)
async def run_session(session_id: str, req: SessionRunRequest):
    session = SESSIONS.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    session.messages.append(("user", req.message))

    state = {
        "messages": session.messages,
        "active_agent": "Coder",
        "loop_count": 0,
        "validator_ok": False,
        "blocked": False,
        "config": session.cfg,
    }

    final_state = await session.app.ainvoke(
        state,
        config={"recursion_limit": session.cfg.recursion_limit},
    )

    # persist updated messages
    session.messages = [
        ("user", m.content) if getattr(m, "type", "") == "human" else ("ai", str(m.content))
        for m in final_state.get("messages", [])
        if getattr(m, "content", None)
    ]  # type: ignore[attr-defined]

    msgs: List[str] = []
    for m in final_state.get("messages", []):
        content = getattr(m, "content", None)
        if content:
            msgs.append(str(content))

    return SessionRunResponse(status="ok", messages=msgs)


def main() -> None:
    import uvicorn

    uvicorn.run("ollama_coder.api:app", host="127.0.0.1", port=8000, reload=False)


if __name__ == "__main__":
    main()


# ----------------------
# Pydantic-AI Orchestrator endpoint
# ----------------------


@app.post("/pydantic/run", response_model=PydOrchResponse)
async def run_pydantic_orchestrator(req: PydOrchRequest):
    deps = OrchestratorDeps(project_root=req.project_root, apply_changes=req.apply_changes)
    result = await orchestrator_agent.run(req.task, deps=deps)
    # result.output is a Pydantic model (OrchestrationSummary)
    return PydOrchResponse(status="ok", summary=result.output.model_dump())


# ----------------------
# OpenAI-compatible Chat Completions endpoint
# ----------------------


@app.post("/v1/chat/completions", response_model=ChatCompletionResponse)
async def chat_completions(req: ChatCompletionRequest):
    """Lightweight OpenAI-style chat completions facade over the supervisor graph."""
    if not req.messages:
        raise HTTPException(status_code=400, detail="messages cannot be empty")

    cfg = RunConfig(
        check_command=req.check_command or None,
        max_loops=req.max_loops,
        recursion_limit=req.recursion_limit,
        coder_model=req.coder_model or req.model or "qwen2.5-coder:7b",
        reviewer_model=req.reviewer_model or "llama3.2",
    )

    graph = await build_graph(cfg)

    initial_state = {
        "messages": [(m.role, m.content) for m in req.messages],
        "active_agent": "Coder",
        "loop_count": 0,
        "validator_ok": False,
        "blocked": False,
        "config": cfg,
    }

    final_state = await graph.ainvoke(
        initial_state,
        config={"recursion_limit": cfg.recursion_limit},
    )

    assistant_content: str | None = None
    for m in reversed(final_state.get("messages", [])):
        role = getattr(m, "type", getattr(m, "role", ""))
        content = getattr(m, "content", None)
        if role in ("ai", "assistant") and content:
            assistant_content = str(content)
            break
    if assistant_content is None:
        for m in reversed(final_state.get("messages", [])):
            content = getattr(m, "content", None)
            if content:
                assistant_content = str(content)
                break

    if assistant_content is None:
        assistant_content = ""

    choice = ChatCompletionChoice(
        index=0,
        message=OpenAIMessage(role="assistant", content=assistant_content),
        finish_reason="stop",
    )

    return ChatCompletionResponse(
        id=f"chatcmpl-{uuid.uuid4().hex}",
        object="chat.completion",
        created=int(time.time()),
        model=cfg.coder_model,
        choices=[choice],
        usage=ChatCompletionUsage(),
    )


# ----------------------
# Batch Processing Endpoints
# ----------------------


class BatchAgentTaskRequest(BaseModel):
    tasks: List[Dict[str, Any]]
    chunk_size: int = 10
    parallel: int = 3
    check_command: str | None = "pytest -q"
    max_loops: int = 16
    coder_model: str = "qwen2.5-coder:7b"
    reviewer_model: str = "llama3.2"


class BatchValidationRequest(BaseModel):
    targets: List[Dict[str, Any]]
    check_command: str = "pytest -q"
    parallel: int = 5


class BatchTestRequest(BaseModel):
    modules: List[Dict[str, Any]]
    test_command: str = "pytest -v"
    parallel: int = 5


class BatchMCPRequest(BaseModel):
    operations: List[Dict[str, Any]]
    parallel: int = 5


class JobResponse(BaseModel):
    job_id: str
    status: str
    progress: float
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    created_at: float
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    metadata: Dict[str, Any] = {}


class JobListResponse(BaseModel):
    jobs: List[JobResponse]
    total: int


class QueueStatsResponse(BaseModel):
    stats: Dict[str, Any]


async def get_batch_queue() -> JobQueue:
    """Get or create batch queue instance."""
    global batch_queue
    if batch_queue is None:
        batch_queue = JobQueue(max_workers=5, chunk_size=100)

        # Register processors
        batch_queue.register_processor(
            "batch_agent_tasks",
            lambda job, queue: BatchAgentProcessor().process(job, queue),
        )
        batch_queue.register_processor(
            "batch_validation",
            lambda job, queue: BatchValidationProcessor().process(job, queue),
        )
        batch_queue.register_processor(
            "batch_tests",
            lambda job, queue: BatchTestProcessor().process(job, queue),
        )
        batch_queue.register_processor(
            "batch_mcp",
            lambda job, queue: BatchMCPProcessor().process(job, queue),
        )

        # Start the queue
        await batch_queue.start()

    return batch_queue


@app.on_event("startup")
async def startup_event():
    """Initialize batch queue on startup."""
    await get_batch_queue()


@app.on_event("shutdown")
async def shutdown_event():
    """Stop batch queue on shutdown."""
    global batch_queue
    if batch_queue:
        await batch_queue.stop()


@app.post("/batch/agent-tasks", response_model=JobResponse)
async def submit_batch_agent_tasks(req: BatchAgentTaskRequest):
    """Submit multiple coding tasks for batch processing.

    Example request body:
    ```json
    {
        "tasks": [
            {"id": "task1", "description": "Create hello.py that prints Hello World"},
            {"id": "task2", "description": "Add unit tests for hello.py"}
        ],
        "chunk_size": 10,
        "parallel": 3
    }
    ```
    """
    queue = await get_batch_queue()

    job = await queue.add_job(
        "batch_agent_tasks",
        {
            "tasks": req.tasks,
            "chunk_size": req.chunk_size,
            "parallel": req.parallel,
            "config": RunConfig(
                check_command=req.check_command,
                max_loops=req.max_loops,
                coder_model=req.coder_model,
                reviewer_model=req.reviewer_model,
            ).__dict__,
        },
        metadata={"total_tasks": len(req.tasks)},
    )

    return JobResponse(
        job_id=job.id,
        status=job.status.value,
        progress=job.progress,
        result=job.result,
        error=job.error,
        created_at=job.created_at,
        started_at=job.started_at,
        completed_at=job.completed_at,
        metadata=job.metadata,
    )


@app.post("/batch/validation", response_model=JobResponse)
async def submit_batch_validation(req: BatchValidationRequest):
    """Submit multiple files/projects for batch validation.

    Example request body:
    ```json
    {
        "targets": [
            {"id": "file1", "path": "src/ollama_coder/core/config.py"},
            {"id": "file2", "path": "src/ollama_coder/core/supervisor.py"}
        ],
        "check_command": "pytest -q",
        "parallel": 5
    }
    ```
    """
    queue = await get_batch_queue()

    job = await queue.add_job(
        "batch_validation",
        {
            "targets": req.targets,
            "check_command": req.check_command,
            "parallel": req.parallel,
        },
        metadata={"total_targets": len(req.targets)},
    )

    return JobResponse(
        job_id=job.id,
        status=job.status.value,
        progress=job.progress,
        result=job.result,
        error=job.error,
        created_at=job.created_at,
        started_at=job.started_at,
        completed_at=job.completed_at,
        metadata=job.metadata,
    )


@app.post("/batch/tests", response_model=JobResponse)
async def submit_batch_tests(req: BatchTestRequest):
    """Submit multiple test modules for batch execution.

    Example request body:
    ```json
    {
        "modules": [
            {"id": "test1", "path": "tests/test_config.py"},
            {"id": "test2", "path": "tests/test_guardrail.py"}
        ],
        "test_command": "pytest -v",
        "parallel": 5
    }
    ```
    """
    queue = await get_batch_queue()

    job = await queue.add_job(
        "batch_tests",
        {
            "modules": req.modules,
            "test_command": req.test_command,
            "parallel": req.parallel,
        },
        metadata={"total_modules": len(req.modules)},
    )

    return JobResponse(
        job_id=job.id,
        status=job.status.value,
        progress=job.progress,
        result=job.result,
        error=job.error,
        created_at=job.created_at,
        started_at=job.started_at,
        completed_at=job.completed_at,
        metadata=job.metadata,
    )


@app.post("/batch/mcp-operations", response_model=JobResponse)
async def submit_batch_mcp_operations(req: BatchMCPRequest):
    """Submit multiple MCP operations for batch processing.

    Example request body:
    ```json
    {
        "operations": [
            {"type": "read", "path": "README.md"},
            {"type": "list", "path": "src/"},
            {"type": "command", "command": "ls -la"}
        ],
        "parallel": 5
    }
    ```
    """
    queue = await get_batch_queue()

    job = await queue.add_job(
        "batch_mcp",
        {
            "operations": req.operations,
            "parallel": req.parallel,
        },
        metadata={"total_operations": len(req.operations)},
    )

    return JobResponse(
        job_id=job.id,
        status=job.status.value,
        progress=job.progress,
        result=job.result,
        error=job.error,
        created_at=job.created_at,
        started_at=job.started_at,
        completed_at=job.completed_at,
        metadata=job.metadata,
    )


@app.get("/batch/jobs/{job_id}", response_model=JobResponse)
async def get_batch_job(job_id: str):
    """Get status and results of a batch job."""
    queue = await get_batch_queue()
    job = await queue.get_job(job_id)

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    return JobResponse(
        job_id=job.id,
        status=job.status.value,
        progress=job.progress,
        result=job.result,
        error=job.error,
        created_at=job.created_at,
        started_at=job.started_at,
        completed_at=job.completed_at,
        metadata=job.metadata,
    )


@app.get("/batch/jobs", response_model=JobListResponse)
async def list_batch_jobs(
    status: Optional[str] = None,
    job_type: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
):
    """List batch jobs with optional filtering."""
    queue = await get_batch_queue()

    job_status = JobStatus(status) if status else None
    jobs = await queue.list_jobs(status=job_status, job_type=job_type, limit=limit, offset=offset)

    job_responses = [
        JobResponse(
            job_id=job.id,
            status=job.status.value,
            progress=job.progress,
            result=job.result,
            error=job.error,
            created_at=job.created_at,
            started_at=job.started_at,
            completed_at=job.completed_at,
            metadata=job.metadata,
        )
        for job in jobs
    ]

    return JobListResponse(jobs=job_responses, total=len(job_responses))


@app.delete("/batch/jobs/{job_id}")
async def cancel_batch_job(job_id: str):
    """Cancel a running or queued batch job."""
    queue = await get_batch_queue()
    cancelled = await queue.cancel_job(job_id)

    if not cancelled:
        raise HTTPException(
            status_code=400,
            detail="Job cannot be cancelled (not found or already completed)",
        )

    return {"status": "cancelled", "job_id": job_id}


@app.get("/batch/stats", response_model=QueueStatsResponse)
async def get_batch_stats():
    """Get batch queue statistics."""
    queue = await get_batch_queue()
    stats = await queue.get_stats()

    return QueueStatsResponse(stats=stats)


# ----------------------
# Celery Batch Processing Endpoints (Alternative Backend)
# ----------------------

try:
    from .batch.celery_tasks import (
        batch_agent_tasks as celery_batch_agent_tasks,
    )
    from .batch.celery_tasks import (
        batch_mcp_operations as celery_batch_mcp_operations,
    )
    from .batch.celery_tasks import (
        batch_tests as celery_batch_tests,
    )
    from .batch.celery_tasks import (
        batch_validation as celery_batch_validation,
    )
    from .batch.celery_tasks import (
        get_group_status,
        get_task_status,
    )

    CELERY_AVAILABLE = True
except ImportError:
    CELERY_AVAILABLE = False


class CeleryBatchRequest(BaseModel):
    """Base request for Celery batch operations."""

    backend: str = "celery"  # Specify to use Celery backend


@app.post("/batch/celery/agent-tasks")
async def submit_celery_batch_agent_tasks(req: BatchAgentTaskRequest):
    """Submit batch agent tasks using Celery (distributed processing).

    Requires:
    - Celery broker (Redis/RabbitMQ) running
    - Celery workers started: celery -A ollama_coder.batch.celery_app worker

    Returns task group ID for monitoring via /batch/celery/group/{group_id}
    """
    if not CELERY_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="Celery backend not available. Install with: pip install celery redis",
        )

    config_dict = {
        "check_command": req.check_command,
        "max_loops": req.max_loops,
        "recursion_limit": 80,
        "coder_model": req.coder_model,
        "reviewer_model": req.reviewer_model,
        "apply_changes": True,
    }

    # Submit to Celery
    group_id = celery_batch_agent_tasks.apply_async(args=[req.tasks, config_dict]).id

    return {
        "backend": "celery",
        "group_id": group_id,
        "status": "submitted",
        "total_tasks": len(req.tasks),
        "monitor_url": f"/batch/celery/group/{group_id}",
    }


@app.post("/batch/celery/validation")
async def submit_celery_batch_validation(req: BatchValidationRequest):
    """Submit batch validation using Celery."""
    if not CELERY_AVAILABLE:
        raise HTTPException(status_code=503, detail="Celery backend not available")

    group_id = celery_batch_validation.apply_async(args=[req.targets, req.check_command]).id

    return {
        "backend": "celery",
        "group_id": group_id,
        "status": "submitted",
        "total_tasks": len(req.targets),
        "monitor_url": f"/batch/celery/group/{group_id}",
    }


@app.post("/batch/celery/tests")
async def submit_celery_batch_tests(req: BatchTestRequest):
    """Submit batch tests using Celery."""
    if not CELERY_AVAILABLE:
        raise HTTPException(status_code=503, detail="Celery backend not available")

    group_id = celery_batch_tests.apply_async(args=[req.modules, req.test_command]).id

    return {
        "backend": "celery",
        "group_id": group_id,
        "status": "submitted",
        "total_tasks": len(req.modules),
        "monitor_url": f"/batch/celery/group/{group_id}",
    }


@app.post("/batch/celery/mcp-operations")
async def submit_celery_batch_mcp(req: BatchMCPRequest):
    """Submit batch MCP operations using Celery."""
    if not CELERY_AVAILABLE:
        raise HTTPException(status_code=503, detail="Celery backend not available")

    group_id = celery_batch_mcp_operations.apply_async(args=[req.operations]).id

    return {
        "backend": "celery",
        "group_id": group_id,
        "status": "submitted",
        "total_tasks": len(req.operations),
        "monitor_url": f"/batch/celery/group/{group_id}",
    }


@app.get("/batch/celery/task/{task_id}")
async def get_celery_task_status(task_id: str):
    """Get status of a single Celery task."""
    if not CELERY_AVAILABLE:
        raise HTTPException(status_code=503, detail="Celery not available")

    return get_task_status(task_id)


@app.get("/batch/celery/group/{group_id}")
async def get_celery_group_status(group_id: str):
    """Get status of a Celery group (batch job).

    Returns progress and individual task results.
    """
    if not CELERY_AVAILABLE:
        raise HTTPException(status_code=503, detail="Celery not available")

    return get_group_status(group_id)
