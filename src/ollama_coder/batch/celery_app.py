"""Celery application configuration for distributed batch processing.

This provides an alternative to the SQLite-based job queue using Celery
for production deployments with Redis/RabbitMQ.

Usage:
    # Start Celery worker
    celery -A ollama_coder.batch.celery_app worker --loglevel=info

    # Start Celery beat (for scheduled tasks)
    celery -A ollama_coder.batch.celery_app beat --loglevel=info

    # Monitor with Flower
    celery -A ollama_coder.batch.celery_app flower
"""

from __future__ import annotations

import os

from celery import Celery
from kombu import Exchange, Queue

# Celery broker configuration
# Supports: Redis, RabbitMQ, Amazon SQS, etc.
BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/0")

# Create Celery app
app = Celery(
    "ollama_coder_batch",
    broker=BROKER_URL,
    backend=RESULT_BACKEND,
    include=[
        "ollama_coder.batch.celery_tasks",
    ],
)

# Celery configuration
app.conf.update(
    # Task settings
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    # Task execution settings
    task_track_started=True,
    task_time_limit=3600,  # 1 hour max per task
    task_soft_time_limit=3300,  # 55 minutes soft limit
    task_acks_late=True,  # Acknowledge after task completion
    task_reject_on_worker_lost=True,
    # Result backend settings
    result_expires=86400,  # Results expire after 24 hours
    result_extended=True,  # Store additional task metadata
    # Worker settings
    worker_prefetch_multiplier=1,  # One task at a time per worker
    worker_max_tasks_per_child=100,  # Restart worker after 100 tasks (memory)
    worker_disable_rate_limits=False,
    # Retry settings
    task_autoretry_for=(Exception,),
    task_retry_kwargs={"max_retries": 3},
    task_retry_backoff=True,
    task_retry_backoff_max=600,  # Max 10 minutes between retries
    task_retry_jitter=True,
    # Queue configuration
    task_default_queue="default",
    task_default_exchange="tasks",
    task_default_routing_key="default",
    # Define queues with priorities
    task_queues=(
        Queue(
            "default",
            Exchange("tasks"),
            routing_key="default",
            priority=5,
        ),
        Queue(
            "high_priority",
            Exchange("tasks"),
            routing_key="high",
            priority=10,
        ),
        Queue(
            "low_priority",
            Exchange("tasks"),
            routing_key="low",
            priority=1,
        ),
        Queue(
            "agent_tasks",
            Exchange("tasks"),
            routing_key="agent",
            priority=7,
        ),
        Queue(
            "validation",
            Exchange("tasks"),
            routing_key="validation",
            priority=6,
        ),
        Queue(
            "tests",
            Exchange("tasks"),
            routing_key="tests",
            priority=6,
        ),
        Queue(
            "mcp_operations",
            Exchange("tasks"),
            routing_key="mcp",
            priority=5,
        ),
    ),
    # Route tasks to specific queues
    task_routes={
        "ollama_coder.batch.celery_tasks.process_agent_task": {
            "queue": "agent_tasks",
            "routing_key": "agent",
        },
        "ollama_coder.batch.celery_tasks.process_validation": {
            "queue": "validation",
            "routing_key": "validation",
        },
        "ollama_coder.batch.celery_tasks.process_test": {
            "queue": "tests",
            "routing_key": "tests",
        },
        "ollama_coder.batch.celery_tasks.process_mcp_operation": {
            "queue": "mcp_operations",
            "routing_key": "mcp",
        },
    },
    # Monitoring
    worker_send_task_events=True,
    task_send_sent_event=True,
    # Security
    task_always_eager=os.getenv("CELERY_ALWAYS_EAGER", "false").lower() == "true",
)

# Beat schedule for periodic tasks (optional)
app.conf.beat_schedule = {
    # Example: Clean up old results every hour
    "cleanup-old-results": {
        "task": "ollama_coder.batch.celery_tasks.cleanup_old_results",
        "schedule": 3600.0,  # Every hour
    },
}


if __name__ == "__main__":
    app.start()
