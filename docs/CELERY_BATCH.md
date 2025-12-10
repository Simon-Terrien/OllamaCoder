# Celery Batch Processing Guide

Production-grade distributed batch processing using Celery for Ollama Coder.

## Overview

The Celery integration provides an alternative to the SQLite-based batch queue for production deployments. It offers:

- **Distributed Processing**: Scale across multiple machines
- **High Availability**: Automatic failover with Redis/RabbitMQ
- **Production Ready**: Battle-tested task queue (millions of users)
- **Advanced Features**: Priorities, retries, monitoring, scheduling
- **Flexibility**: Multiple broker backends (Redis, RabbitMQ, SQS, etc.)

## Architecture

```
API Server → Celery Broker (Redis/RabbitMQ) → Multiple Workers
                     ↓
             Result Backend (Redis)
                     ↓
              Task Results
```

## Installation

### Option 1: Redis Backend (Recommended)

```bash
# Install with Redis support
uv pip install -e ".[celery]"

# Or with pip
pip install -e ".[celery]"
```

### Option 2: RabbitMQ Backend

```bash
# Install with RabbitMQ support
uv pip install -e ".[rabbitmq]"
```

### Start Broker

#### Redis
```bash
# Using Docker
docker run -d -p 6379:6379 redis:latest

# Or install locally
# Ubuntu/Debian
sudo apt-get install redis-server
sudo systemctl start redis

# macOS
brew install redis
brew services start redis
```

#### RabbitMQ
```bash
# Using Docker
docker run -d -p 5672:5672 -p 15672:15672 rabbitmq:management

# Or install locally
# Ubuntu/Debian
sudo apt-get install rabbitmq-server
sudo systemctl start rabbitmq-server

# macOS
brew install rabbitmq
brew services start rabbitmq
```

## Quick Start

### 1. Start Celery Workers

```bash
# Start a Celery worker
celery -A ollama_coder.batch.celery_app worker --loglevel=info

# Start multiple workers (scale up)
celery -A ollama_coder.batch.celery_app worker --loglevel=info --concurrency=4

# Start worker for specific queue
celery -A ollama_coder.batch.celery_app worker -Q agent_tasks --loglevel=info
```

### 2. Start Monitoring UI (Optional)

```bash
# Start Flower (Celery monitoring web UI)
celery -A ollama_coder.batch.celery_app flower

# Open http://localhost:5555 in browser
```

### 3. Start API Server

```bash
uv run python -m ollama_coder.api
```

### 4. Submit Batch Jobs

```bash
# Submit batch agent tasks via Celery
curl -X POST http://127.0.0.1:8000/batch/celery/agent-tasks \
  -H "Content-Type: application/json" \
  -d '{
    "tasks": [
      {"id": "task1", "description": "Create hello.py"},
      {"id": "task2", "description": "Add tests"}
    ],
    "parallel": 3
  }'

# Response:
{
  "backend": "celery",
  "group_id": "a1b2c3d4-e5f6-7g8h-9i0j-k1l2m3n4o5p6",
  "status": "submitted",
  "total_tasks": 2,
  "monitor_url": "/batch/celery/group/a1b2c3d4..."
}
```

### 5. Monitor Progress

```bash
# Check group status
curl http://127.0.0.1:8000/batch/celery/group/a1b2c3d4-e5f6-7g8h-9i0j-k1l2m3n4o5p6

# Response:
{
  "group_id": "a1b2c3d4...",
  "total": 2,
  "completed": 2,
  "successful": 2,
  "failed": 0,
  "progress": 100.0,
  "ready": true,
  "results": [
    {"status": "completed", "result": {...}},
    {"status": "completed", "result": {...}}
  ]
}
```

## API Endpoints

### Celery Batch Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/batch/celery/agent-tasks` | POST | Submit agent tasks to Celery |
| `/batch/celery/validation` | POST | Submit validation jobs |
| `/batch/celery/tests` | POST | Submit test jobs |
| `/batch/celery/mcp-operations` | POST | Submit MCP operations |
| `/batch/celery/task/{task_id}` | GET | Get single task status |
| `/batch/celery/group/{group_id}` | GET | Get batch job status |

## Configuration

### Environment Variables

```bash
# Broker URL (default: Redis)
export CELERY_BROKER_URL="redis://localhost:6379/0"

# Result backend
export CELERY_RESULT_BACKEND="redis://localhost:6379/0"

# For RabbitMQ
export CELERY_BROKER_URL="amqp://guest:guest@localhost:5672//"
export CELERY_RESULT_BACKEND="rpc://"

# For development (synchronous execution)
export CELERY_ALWAYS_EAGER="true"
```

### Celery Configuration

Edit `src/ollama_coder/batch/celery_app.py` to customize:

```python
app.conf.update(
    # Task settings
    task_time_limit=3600,  # 1 hour max
    task_soft_time_limit=3300,  # 55 minutes soft limit

    # Worker settings
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=100,

    # Retry settings
    task_autoretry_for=(Exception,),
    task_retry_kwargs={"max_retries": 3},
)
```

## Queue Management

### Priority Queues

Tasks are routed to specific queues with priorities:

| Queue | Priority | Task Type |
|-------|----------|-----------|
| `high_priority` | 10 | Critical tasks |
| `agent_tasks` | 7 | Agent operations |
| `validation` | 6 | Code validation |
| `tests` | 6 | Test execution |
| `default` | 5 | General tasks |
| `mcp_operations` | 5 | MCP operations |
| `low_priority` | 1 | Background tasks |

### Start Queue-Specific Workers

```bash
# High-priority worker
celery -A ollama_coder.batch.celery_app worker -Q high_priority --loglevel=info

# Agent tasks only
celery -A ollama_coder.batch.celery_app worker -Q agent_tasks --loglevel=info

# Multiple queues
celery -A ollama_coder.batch.celery_app worker -Q agent_tasks,validation --loglevel=info
```

## Scaling

### Horizontal Scaling

```bash
# Start multiple workers on same machine
celery multi start worker1 worker2 worker3 \
  -A ollama_coder.batch.celery_app \
  --loglevel=info

# Start workers on different machines
# Machine 1:
celery -A ollama_coder.batch.celery_app worker --hostname=worker1@machine1

# Machine 2:
celery -A ollama_coder.batch.celery_app worker --hostname=worker2@machine2

# Machine 3:
celery -A ollama_coder.batch.celery_app worker --hostname=worker3@machine3
```

### Autoscaling

```bash
# Autoscale between 2-8 workers
celery -A ollama_coder.batch.celery_app worker \
  --autoscale=8,2 \
  --loglevel=info
```

## Monitoring

### Flower Web UI

```bash
# Start Flower
celery -A ollama_coder.batch.celery_app flower

# Open http://localhost:5555
# Features:
# - Real-time task monitoring
# - Worker statistics
# - Task history
# - Retry failed tasks
# - Task routing visualization
```

### Command Line Monitoring

```bash
# List active workers
celery -A ollama_coder.batch.celery_app inspect active

# Get worker stats
celery -A ollama_coder.batch.celery_app inspect stats

# List active tasks
celery -A ollama_coder.batch.celery_app inspect active

# List registered tasks
celery -A ollama_coder.batch.celery_app inspect registered

# Purge all tasks
celery -A ollama_coder.batch.celery_app purge
```

## Comparison: SQLite vs Celery

| Feature | SQLite Queue | Celery |
|---------|-------------|--------|
| **Setup** | No dependencies | Requires broker (Redis/RabbitMQ) |
| **Scaling** | Single machine | Multi-machine |
| **Performance** | 100-1000 tasks/min | Millions of tasks/min |
| **Persistence** | SQLite file | Broker + result backend |
| **Monitoring** | Basic API | Flower UI + CLI tools |
| **Production** | Small deployments | Enterprise scale |
| **Cost** | Free | Broker hosting costs |
| **Reliability** | Good | Excellent (HA support) |

### When to Use Each

**Use SQLite Queue when:**
- Single machine deployment
- < 1000 tasks/day
- Simple setup preferred
- No external dependencies desired

**Use Celery when:**
- Multi-machine deployment needed
- High throughput (1000s of tasks)
- Production environment
- Advanced features needed (priorities, scheduling)
- High availability required

## Examples

### Example 1: Distribute 1000 Tasks

```python
import requests

# Generate 1000 tasks
tasks = [
    {"id": f"task-{i}", "description": f"Process item {i}"}
    for i in range(1000)
]

# Submit to Celery
response = requests.post(
    "http://127.0.0.1:8000/batch/celery/agent-tasks",
    json={"tasks": tasks, "parallel": 10}
)

group_id = response.json()["group_id"]
print(f"Submitted {len(tasks)} tasks to Celery")
print(f"Group ID: {group_id}")

# Monitor with Flower at http://localhost:5555
```

### Example 2: Priority Tasks

```python
# High-priority tasks get processed first
# Configure in celery_app.py or submit to high_priority queue

from ollama_coder.batch.celery_tasks import process_agent_task

# Submit high-priority task
result = process_agent_task.apply_async(
    args=[task_data, config_dict],
    queue="high_priority"
)
```

### Example 3: Scheduled Batch Jobs

```python
# Schedule a batch job for later
from datetime import datetime, timedelta
from ollama_coder.batch.celery_tasks import batch_agent_tasks

# Run in 1 hour
eta = datetime.now() + timedelta(hours=1)

result = batch_agent_tasks.apply_async(
    args=[tasks, config_dict],
    eta=eta
)
```

## Production Deployment

### Docker Compose Setup

Create `docker-compose.yml`:

```yaml
version: '3.8'

services:
  redis:
    image: redis:latest
    ports:
      - "6379:6379"
    volumes:
      - redis-data:/data

  celery-worker:
    build: .
    command: celery -A ollama_coder.batch.celery_app worker --loglevel=info
    depends_on:
      - redis
    environment:
      - CELERY_BROKER_URL=redis://redis:6379/0
      - CELERY_RESULT_BACKEND=redis://redis:6379/0
    deploy:
      replicas: 3  # 3 workers

  flower:
    build: .
    command: celery -A ollama_coder.batch.celery_app flower
    ports:
      - "5555:5555"
    depends_on:
      - redis
      - celery-worker
    environment:
      - CELERY_BROKER_URL=redis://redis:6379/0

  api:
    build: .
    command: uvicorn ollama_coder.api:app --host 0.0.0.0 --port 8000
    ports:
      - "8000:8000"
    depends_on:
      - redis
    environment:
      - CELERY_BROKER_URL=redis://redis:6379/0
      - CELERY_RESULT_BACKEND=redis://redis:6379/0

volumes:
  redis-data:
```

Start with:
```bash
docker-compose up -d
docker-compose scale celery-worker=5  # Scale to 5 workers
```

### Systemd Service (Linux)

Create `/etc/systemd/system/ollama-coder-celery.service`:

```ini
[Unit]
Description=Ollama Coder Celery Worker
After=network.target redis.service

[Service]
Type=forking
User=ollama-coder
WorkingDirectory=/opt/ollama-coder
Environment="CELERY_BROKER_URL=redis://localhost:6379/0"
ExecStart=/opt/ollama-coder/venv/bin/celery multi start worker1 \
  -A ollama_coder.batch.celery_app \
  --pidfile=/var/run/celery/%n.pid \
  --logfile=/var/log/celery/%n%I.log \
  --loglevel=INFO
ExecStop=/opt/ollama-coder/venv/bin/celery multi stopwait worker1 \
  --pidfile=/var/run/celery/%n.pid
ExecReload=/opt/ollama-coder/venv/bin/celery multi restart worker1 \
  -A ollama_coder.batch.celery_app \
  --pidfile=/var/run/celery/%n.pid \
  --logfile=/var/log/celery/%n%I.log \
  --loglevel=INFO
Restart=always

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl enable ollama-coder-celery
sudo systemctl start ollama-coder-celery
sudo systemctl status ollama-coder-celery
```

## Troubleshooting

### Worker Not Starting

**Symptoms**: Worker crashes or doesn't connect

**Solutions**:
1. Check broker is running: `redis-cli ping` or `rabbitmqctl status`
2. Verify connection URL in environment
3. Check logs: `celery -A ollama_coder.batch.celery_app worker --loglevel=debug`

### Tasks Not Processing

**Symptoms**: Tasks stuck in queue

**Solutions**:
1. Check workers are running: `celery -A ollama_coder.batch.celery_app inspect active`
2. Verify queue routing configuration
3. Check task time limits
4. Inspect worker logs

### High Memory Usage

**Symptoms**: Workers consuming too much memory

**Solutions**:
1. Reduce `worker_prefetch_multiplier`
2. Lower `worker_max_tasks_per_child` (restart workers more often)
3. Scale out (more workers, less concurrency each)

### Connection Issues

**Symptoms**: "Connection refused" or timeout errors

**Solutions**:
1. Check firewall rules
2. Verify broker URL and port
3. Test connection: `redis-cli -h localhost -p 6379 ping`
4. Check broker logs

## Best Practices

1. **Use Redis for small-medium deployments** - Simpler than RabbitMQ
2. **RabbitMQ for large-scale** - Better for high throughput
3. **Set task time limits** - Prevent runaway tasks
4. **Enable task acknowledgment** - `task_acks_late=True`
5. **Use priorities wisely** - Don't put everything in high priority
6. **Monitor with Flower** - Essential for production
7. **Implement retries** - Handle transient failures
8. **Log everything** - Helps with debugging
9. **Test with `CELERY_ALWAYS_EAGER`** - Synchronous execution for testing
10. **Scale horizontally** - Add more workers instead of increasing concurrency

## Security

1. **Protect broker** - Use authentication (Redis password, RabbitMQ users)
2. **Secure Flower** - Enable authentication: `celery flower --basic_auth=user:password`
3. **Network isolation** - Firewall broker from public internet
4. **Encrypt connections** - Use SSL/TLS for broker connections
5. **Validate task inputs** - Don't trust task data
6. **Limit task execution time** - Prevent resource exhaustion

## Additional Resources

- [Celery Documentation](https://docs.celeryproject.org/)
- [Redis Documentation](https://redis.io/documentation)
- [RabbitMQ Documentation](https://www.rabbitmq.com/documentation.html)
- [Flower Documentation](https://flower.readthedocs.io/)
- [Celery Best Practices](https://docs.celeryproject.org/en/stable/userguide/tasks.html#best-practices)
