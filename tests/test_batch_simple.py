"""Simple tests for batch processing that don't require full dependencies."""
import sys
from pathlib import Path

def test_progress_tracker():
    """Test progress tracking functionality."""
    from ollama_coder.batch.progress import ProgressTracker

    tracker = ProgressTracker(total=100)

    assert tracker.percentage == 0.0
    assert tracker.processed == 0
    assert tracker.successful == 0
    assert tracker.failed == 0

    # Increment successes
    for i in range(50):
        tracker.increment(success=True)

    assert tracker.processed == 50
    assert tracker.successful == 50
    assert tracker.failed == 0
    assert tracker.percentage == 50.0

    # Increment failures
    for i in range(30):
        tracker.increment(success=False)

    assert tracker.processed == 80
    assert tracker.successful == 50
    assert tracker.failed == 30
    assert tracker.percentage == 80.0

    # Increment skipped
    for i in range(20):
        tracker.increment(skip=True)

    assert tracker.processed == 100
    assert tracker.skipped == 20
    assert tracker.percentage == 100.0

    # Test to_dict
    data = tracker.to_dict()
    assert data["total"] == 100
    assert data["processed"] == 100
    assert data["successful"] == 50
    assert data["failed"] == 30
    assert data["skipped"] == 20
    assert data["percentage"] == 100.0


def test_job_status_enum():
    """Test job status enumeration."""
    from ollama_coder.batch.job_queue import JobStatus

    assert JobStatus.QUEUED == "queued"
    assert JobStatus.RUNNING == "running"
    assert JobStatus.COMPLETED == "completed"
    assert JobStatus.FAILED == "failed"
    assert JobStatus.CANCELLED == "cancelled"


def test_job_to_dict():
    """Test job serialization."""
    from ollama_coder.batch.job_queue import Job, JobStatus

    job = Job(
        id="test-123",
        type="test_type",
        data={"key": "value"},
        status=JobStatus.QUEUED,
        metadata={"test": True},
    )

    job_dict = job.to_dict()

    assert job_dict["id"] == "test-123"
    assert job_dict["type"] == "test_type"
    assert job_dict["data"] == {"key": "value"}
    assert job_dict["status"] == "queued"
    assert job_dict["metadata"] == {"test": True}
    assert job_dict["progress"] == 0.0


def test_job_from_dict():
    """Test job deserialization."""
    from ollama_coder.batch.job_queue import Job, JobStatus

    data = {
        "id": "test-456",
        "type": "test_type",
        "data": {"foo": "bar"},
        "status": "running",
        "progress": 50.0,
        "result": {"output": "success"},
        "error": None,
        "created_at": 1234567890.0,
        "started_at": 1234567891.0,
        "completed_at": None,
        "metadata": {"workers": 5},
    }

    job = Job.from_dict(data)

    assert job.id == "test-456"
    assert job.type == "test_type"
    assert job.data == {"foo": "bar"}
    assert job.status == JobStatus.RUNNING
    assert job.progress == 50.0
    assert job.result == {"output": "success"}
    assert job.metadata == {"workers": 5}
