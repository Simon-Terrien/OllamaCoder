"""Batch processing module for Ollama Coder.

Provides parallel processing capabilities for:
- Agent tasks (thousands of coding tasks)
- Code validation (multiple files/projects)
- Test execution (multiple modules)
- MCP operations (bulk filesystem operations)
- API requests (bulk task submissions)
"""
from __future__ import annotations

from .job_queue import JobQueue, JobStatus, Job
from .processors import (
    BatchAgentProcessor,
    BatchValidationProcessor,
    BatchTestProcessor,
    BatchMCPProcessor,
)
from .progress import ProgressTracker

__all__ = [
    "JobQueue",
    "JobStatus",
    "Job",
    "BatchAgentProcessor",
    "BatchValidationProcessor",
    "BatchTestProcessor",
    "BatchMCPProcessor",
    "ProgressTracker",
]
