# Batch Processing Guide

Comprehensive guide for using the batch processing capabilities in Ollama Coder.

## Overview

The batch processing module enables parallel execution of thousands of operations including:

1. **Agent Tasks** - Process multiple coding tasks through the agent system
2. **Code Validation** - Validate multiple files or projects simultaneously
3. **Test Execution** - Run tests across multiple modules in parallel
4. **MCP Operations** - Perform bulk filesystem operations
5. **API Requests** - Submit and track batch operations via REST API

## Architecture

### Components

- **JobQueue** - SQLite-backed async job queue with worker pool
- **Processors** - Specialized processors for different operation types
- **ProgressTracker** - Real-time progress tracking and metrics
- **API Endpoints** - RESTful API for job submission and monitoring

### Flow

```
Client → API Endpoint → JobQueue → Worker Pool → Processor → Results
                            ↓
                        SQLite DB (persistence)
                            ↓
                     Progress Updates
```

## Quick Start

### 1. Start the API Server

```bash
uv run python -m ollama_coder.api
```

The batch queue starts automatically with 5 workers.

### 2. Submit a Batch Job

```bash
curl -X POST http://127.0.0.1:8000/batch/agent-tasks \
  -H "Content-Type: application/json" \
  -d '{
    "tasks": [
      {"id": "task1", "description": "Create hello.py that prints Hello World"},
      {"id": "task2", "description": "Add unit tests for hello.py"}
    ],
    "parallel": 3
  }'
```

Response:
```json
{
  "job_id": "batch_agent_tasks-a1b2c3d4e5f6",
  "status": "queued",
  "progress": 0.0,
  "created_at": 1234567890.123,
  "metadata": {"total_tasks": 2}
}
```

### 3. Check Job Status

```bash
curl http://127.0.0.1:8000/batch/jobs/batch_agent_tasks-a1b2c3d4e5f6
```

Response:
```json
{
  "job_id": "batch_agent_tasks-a1b2c3d4e5f6",
  "status": "completed",
  "progress": 100.0,
  "result": {
    "summary": {
      "total": 2,
      "successful": 2,
      "failed": 0,
      "skipped": 0
    },
    "results": [...],
    "elapsed_seconds": 45.2
  },
  "completed_at": 1234567935.321
}
```

## API Endpoints

### Submit Batch Agent Tasks

**POST** `/batch/agent-tasks`

Process multiple coding tasks through the agent system.

**Request Body:**
```json
{
  "tasks": [
    {"id": "task1", "description": "Create a function to calculate fibonacci"},
    {"id": "task2", "description": "Add error handling to the function"},
    {"id": "task3", "description": "Write unit tests"}
  ],
  "chunk_size": 10,
  "parallel": 3,
  "check_command": "pytest -q",
  "max_loops": 16,
  "coder_model": "qwen2.5-coder:7b",
  "reviewer_model": "llama3.2"
}
```

**Response:** `JobResponse`

---

### Submit Batch Validation

**POST** `/batch/validation`

Validate multiple files or projects in parallel.

**Request Body:**
```json
{
  "targets": [
    {"id": "file1", "path": "src/ollama_coder/core/config.py"},
    {"id": "file2", "path": "src/ollama_coder/core/supervisor.py"},
    {"id": "project1", "path": "src/ollama_coder"}
  ],
  "check_command": "pytest -q",
  "parallel": 5
}
```

**Response:** `JobResponse`

---

### Submit Batch Tests

**POST** `/batch/tests`

Execute tests across multiple modules in parallel.

**Request Body:**
```json
{
  "modules": [
    {"id": "test_config", "path": "tests/test_config.py"},
    {"id": "test_guardrail", "path": "tests/test_guardrail.py"},
    {"id": "test_batch", "path": "tests/test_batch_processing.py"}
  ],
  "test_command": "pytest -v",
  "parallel": 5
}
```

**Response:** `JobResponse`

---

### Submit Batch MCP Operations

**POST** `/batch/mcp-operations`

Perform bulk filesystem operations through MCP.

**Request Body:**
```json
{
  "operations": [
    {"type": "read", "path": "README.md"},
    {"type": "list", "path": "src/"},
    {"type": "write", "path": "output.txt", "content": "Hello World"},
    {"type": "command", "command": "ls -la"}
  ],
  "parallel": 5
}
```

**Response:** `JobResponse`

---

### Get Job Status

**GET** `/batch/jobs/{job_id}`

Get the status and results of a specific job.

**Response:**
```json
{
  "job_id": "batch_agent_tasks-abc123",
  "status": "running",
  "progress": 45.5,
  "result": null,
  "error": null,
  "created_at": 1234567890.0,
  "started_at": 1234567891.0,
  "completed_at": null,
  "metadata": {
    "progress": {
      "total": 100,
      "processed": 45,
      "successful": 43,
      "failed": 2,
      "percentage": 45.5,
      "elapsed_seconds": 23.4,
      "items_per_second": 1.92,
      "estimated_remaining_seconds": 28.6
    }
  }
}
```

---

### List Jobs

**GET** `/batch/jobs?status=completed&job_type=batch_agent_tasks&limit=50&offset=0`

List batch jobs with optional filtering.

**Query Parameters:**
- `status` - Filter by job status (queued, running, completed, failed, cancelled)
- `job_type` - Filter by job type
- `limit` - Maximum results (default: 100)
- `offset` - Result offset (default: 0)

**Response:**
```json
{
  "jobs": [...],
  "total": 42
}
```

---

### Cancel Job

**DELETE** `/batch/jobs/{job_id}`

Cancel a running or queued job.

**Response:**
```json
{
  "status": "cancelled",
  "job_id": "batch_agent_tasks-abc123"
}
```

---

### Get Queue Statistics

**GET** `/batch/stats`

Get batch queue statistics.

**Response:**
```json
{
  "stats": {
    "total": 156,
    "queued": 23,
    "running": 5,
    "completed": 120,
    "failed": 7,
    "cancelled": 1
  }
}
```

## Job Statuses

- **queued** - Job is waiting in queue
- **running** - Job is being processed
- **completed** - Job completed successfully
- **failed** - Job failed with error
- **cancelled** - Job was cancelled by user

## Configuration

### Queue Configuration

The batch queue is configured when the API starts:

```python
batch_queue = JobQueue(
    db_path="data/batch_jobs.db",  # SQLite database path
    max_workers=5,                  # Number of parallel workers
    chunk_size=100                  # Items per processing chunk
)
```

### Processor Configuration

Each processor can be configured with specific parameters:

**BatchAgentProcessor:**
- Uses RunConfig for agent behavior
- Configurable models, max loops, validation command

**BatchValidationProcessor:**
- Custom validation command (default: `pytest -q`)
- Parallel execution limit

**BatchTestProcessor:**
- Custom test command (default: `pytest -v`)
- Parallel execution limit

**BatchMCPProcessor:**
- Supports read, write, list, command operations
- Parallel execution limit

## Performance Guidelines

### Throughput Estimates

- **Agent Tasks**: 0.5-2 tasks/second (depending on complexity and model speed)
- **Code Validation**: 5-20 files/second
- **Test Execution**: 2-10 modules/second
- **MCP Operations**: 10-50 operations/second

### Optimization Tips

1. **Chunk Size**: Larger chunks (100-500) for simple operations, smaller (10-50) for complex
2. **Parallel Workers**: Set to CPU cores (typically 4-8 for optimal performance)
3. **Operation Batching**: Group similar operations together for better cache locality
4. **Model Selection**: Use faster models (7B) for batch operations, reserve larger models (14B+) for critical tasks

### Resource Usage

- **Memory**: ~512MB per worker + ~1KB per job in queue
- **Disk**: SQLite database grows ~1-2KB per job (with results)
- **Network**: Agent tasks require Ollama API access

## Error Handling

### Automatic Retries

Jobs are NOT automatically retried. For retry logic:

1. Check failed jobs: `GET /batch/jobs?status=failed`
2. Extract failed items from result
3. Resubmit as new batch job

### Error Recovery

```python
# Python example
import requests

# Get failed job
response = requests.get("http://127.0.0.1:8000/batch/jobs/job-123")
job = response.json()

if job["status"] == "failed":
    # Extract failed items
    failed_items = [
        r for r in job["result"]["results"]
        if r["status"] == "failed"
    ]

    # Resubmit
    requests.post("http://127.0.0.1:8000/batch/agent-tasks", json={
        "tasks": failed_items
    })
```

### Common Errors

**"No processor registered"**
- Cause: Invalid job type
- Solution: Use correct endpoint for job type

**"Job cannot be cancelled"**
- Cause: Job already completed or not found
- Solution: Check job status before cancelling

**Job stuck in "running"**
- Cause: Worker crashed or server restarted
- Solution: Restart API server (jobs will resume from queue)

## Examples

### Example 1: Batch Process 1000 Coding Tasks

```python
import requests
import time

# Generate 1000 tasks
tasks = [
    {
        "id": f"task-{i}",
        "description": f"Create function_{i}.py with a function that returns {i}"
    }
    for i in range(1000)
]

# Submit batch job
response = requests.post(
    "http://127.0.0.1:8000/batch/agent-tasks",
    json={
        "tasks": tasks,
        "chunk_size": 50,  # Process 50 at a time
        "parallel": 5,      # 5 parallel executions per chunk
    }
)

job = response.json()
job_id = job["job_id"]

# Poll for completion
while True:
    response = requests.get(f"http://127.0.0.1:8000/batch/jobs/{job_id}")
    job = response.json()

    print(f"Progress: {job['progress']:.1f}%")

    if job["status"] in ["completed", "failed", "cancelled"]:
        break

    time.sleep(5)

# Print results
result = job["result"]
print(f"Completed: {result['summary']['successful']} tasks")
print(f"Failed: {result['summary']['failed']} tasks")
print(f"Time: {result['elapsed_seconds']:.1f}s")
```

### Example 2: Validate Entire Codebase

```python
import requests
from pathlib import Path

# Find all Python files
python_files = list(Path("src").rglob("*.py"))

targets = [
    {"id": str(f), "path": str(f)}
    for f in python_files
]

# Submit validation
response = requests.post(
    "http://127.0.0.1:8000/batch/validation",
    json={
        "targets": targets,
        "check_command": "ruff check",
        "parallel": 10
    }
)

job_id = response.json()["job_id"]
print(f"Validating {len(targets)} files...")
```

### Example 3: Run All Tests in Parallel

```python
import requests
from pathlib import Path

# Find all test files
test_files = list(Path("tests").glob("test_*.py"))

modules = [
    {"id": f.stem, "path": str(f)}
    for f in test_files
]

# Submit tests
response = requests.post(
    "http://127.0.0.1:8000/batch/tests",
    json={
        "modules": modules,
        "test_command": "pytest -v",
        "parallel": 5
    }
)

print(f"Running {len(modules)} test modules...")
```

### Example 4: Bulk File Operations

```python
import requests

operations = []

# Read multiple files
for i in range(10):
    operations.append({
        "type": "read",
        "path": f"src/module_{i}.py"
    })

# Write results
for i in range(10):
    operations.append({
        "type": "write",
        "path": f"output/result_{i}.txt",
        "content": f"Result {i}"
    })

# Submit MCP operations
response = requests.post(
    "http://127.0.0.1:8000/batch/mcp-operations",
    json={
        "operations": operations,
        "parallel": 10
    }
)

print(f"Processing {len(operations)} operations...")
```

## Monitoring and Observability

### Progress Tracking

Jobs include detailed progress metadata:

```json
{
  "metadata": {
    "progress": {
      "total": 1000,
      "processed": 456,
      "successful": 450,
      "failed": 6,
      "skipped": 0,
      "percentage": 45.6,
      "elapsed_seconds": 234.5,
      "items_per_second": 1.94,
      "estimated_remaining_seconds": 280.3,
      "current_item": "task-456"
    }
  }
}
```

### Metrics

Monitor these key metrics:

- **Throughput**: `items_per_second`
- **Success Rate**: `successful / total`
- **Queue Depth**: Number of queued jobs
- **Worker Utilization**: Running jobs / max_workers

### Logging

Jobs are persisted in SQLite database at `data/batch_jobs.db`.

Query directly for analysis:

```sql
-- Success rate by job type
SELECT
    type,
    COUNT(*) as total,
    SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed,
    AVG(completed_at - started_at) as avg_duration
FROM jobs
GROUP BY type;
```

## Best Practices

1. **Batch Similar Operations**: Group similar tasks together for better performance
2. **Monitor Progress**: Use metadata progress tracking to estimate completion time
3. **Handle Failures Gracefully**: Check results and resubmit failed items
4. **Limit Concurrency**: Don't exceed system resources (use `parallel` parameter)
5. **Clean Up**: Periodically delete old completed jobs from database
6. **Use Appropriate Models**: Faster models for batch operations
7. **Test Small First**: Test with small batches before scaling up
8. **Set Realistic Timeouts**: Allow enough time for complex operations

## Troubleshooting

### Jobs Not Processing

**Symptoms**: Jobs stuck in "queued" status

**Solutions**:
1. Check API server logs for errors
2. Verify workers are running: `GET /batch/stats`
3. Check database permissions
4. Restart API server

### Slow Processing

**Symptoms**: Low `items_per_second`

**Solutions**:
1. Increase `parallel` parameter
2. Increase `max_workers` in queue config
3. Use faster models
4. Optimize chunk size

### High Memory Usage

**Symptoms**: Server memory increasing

**Solutions**:
1. Reduce `max_workers`
2. Reduce `chunk_size`
3. Limit concurrent batch jobs
4. Clean up completed jobs

### Database Locked Errors

**Symptoms**: SQLite database lock errors

**Solutions**:
1. Reduce worker count
2. Use WAL mode for SQLite
3. Avoid concurrent writes from multiple processes

## Security Considerations

1. **Guardrails Apply**: All agent operations go through security guardrails
2. **MCP Operations**: Be cautious with write and command operations
3. **Input Validation**: Validate all job data before submission
4. **Rate Limiting**: Implement rate limiting for API endpoints
5. **Authentication**: Add authentication for production deployments

## Future Enhancements

Potential future additions:

- Job priorities and scheduling
- Distributed workers (multi-server)
- Redis backend option
- Real-time WebSocket updates
- Job dependencies and workflows
- Automatic retries with exponential backoff
- Result caching and deduplication
