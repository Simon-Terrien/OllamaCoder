"""Tests for batch processing functionality."""

from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

import pytest
import pytest_asyncio

from ollama_coder.batch import (
    BatchMCPProcessor,
    BatchTestProcessor,
    BatchValidationProcessor,
    JobQueue,
    JobStatus,
    ProgressTracker,
)


@pytest_asyncio.fixture
async def job_queue():
    """Create a temporary job queue for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_jobs.db"
        queue = JobQueue(db_path=db_path, max_workers=2, chunk_size=10)
        await queue.start()
        yield queue
        await queue.stop()


@pytest.mark.asyncio
async def test_job_queue_add_and_get(job_queue):
    """Test adding and retrieving jobs."""
    job = await job_queue.add_job(
        "test_type",
        {"key": "value"},
        metadata={"test": True},
    )

    assert job.id.startswith("test_type-")
    assert job.type == "test_type"
    assert job.data == {"key": "value"}
    assert job.status == JobStatus.QUEUED
    assert job.metadata == {"test": True}

    # Retrieve job
    retrieved = await job_queue.get_job(job.id)
    assert retrieved is not None
    assert retrieved.id == job.id
    assert retrieved.type == job.type


@pytest.mark.asyncio
async def test_job_queue_list_jobs(job_queue):
    """Test listing jobs with filtering."""
    # Add multiple jobs
    await job_queue.add_job("type1", {"data": 1})
    await job_queue.add_job("type2", {"data": 2})
    await job_queue.add_job("type1", {"data": 3})

    # List all jobs
    all_jobs = await job_queue.list_jobs()
    assert len(all_jobs) >= 3

    # Filter by type
    type1_jobs = await job_queue.list_jobs(job_type="type1")
    assert len(type1_jobs) == 2
    assert all(j.type == "type1" for j in type1_jobs)

    # Filter by status
    queued_jobs = await job_queue.list_jobs(status=JobStatus.QUEUED)
    assert len(queued_jobs) >= 3


@pytest.mark.asyncio
async def test_job_queue_process_job(job_queue):
    """Test job processing with a simple processor."""

    async def simple_processor(job, queue):
        """Simple processor that returns processed data."""
        await asyncio.sleep(0.1)  # Simulate work
        return {"processed": job.data["value"] * 2}

    # Register processor
    job_queue.register_processor("simple", simple_processor)

    # Add job
    job = await job_queue.add_job("simple", {"value": 5})

    # Wait for processing (poll up to 1.5s to avoid flakiness)
    processed_job = None
    for _ in range(15):
        processed_job = await job_queue.get_job(job.id)
        if processed_job and processed_job.status == JobStatus.COMPLETED:
            break
        await asyncio.sleep(0.1)

    assert processed_job is not None
    assert processed_job.status == JobStatus.COMPLETED
    assert processed_job.result == {"processed": 10}
    assert processed_job.progress == 100.0


@pytest.mark.asyncio
async def test_job_queue_cancel_job(job_queue):
    """Test job cancellation."""
    job = await job_queue.add_job("test", {"data": "test"})

    # Cancel job
    cancelled = await job_queue.cancel_job(job.id)
    assert cancelled is True

    # Verify cancelled
    cancelled_job = await job_queue.get_job(job.id)
    assert cancelled_job.status == JobStatus.CANCELLED


@pytest.mark.asyncio
async def test_job_queue_stats(job_queue):
    """Test queue statistics."""
    # Add jobs
    await job_queue.add_job("test1", {})
    await job_queue.add_job("test2", {})

    # Get stats
    stats = await job_queue.get_stats()
    assert "total" in stats
    assert stats["total"] >= 2
    assert "queued" in stats


def test_progress_tracker():
    """Test progress tracking functionality."""
    tracker = ProgressTracker(total=100)

    assert tracker.percentage == 0.0
    assert tracker.processed == 0
    assert tracker.successful == 0
    assert tracker.failed == 0

    # Increment successes
    for _ in range(50):
        tracker.increment(success=True)

    assert tracker.processed == 50
    assert tracker.successful == 50
    assert tracker.failed == 0
    assert tracker.percentage == 50.0

    # Increment failures
    for _ in range(30):
        tracker.increment(success=False)

    assert tracker.processed == 80
    assert tracker.successful == 50
    assert tracker.failed == 30
    assert tracker.percentage == 80.0

    # Increment skipped
    for _ in range(20):
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


def test_progress_tracker_rate_calculation():
    """Test progress tracking rate calculations."""
    import time

    tracker = ProgressTracker(total=100)

    # Process some items
    time.sleep(0.1)
    for _ in range(10):
        tracker.increment(success=True)
        time.sleep(0.01)

    # Check rates
    assert tracker.items_per_second > 0
    assert tracker.estimated_remaining_seconds > 0


@pytest.mark.asyncio
async def test_batch_validation_processor():
    """Test batch validation processor."""
    processor = BatchValidationProcessor(check_command="echo")

    # Create mock job
    job_data = {
        "targets": [
            {"id": "test1", "path": "test.py"},
            {"id": "test2", "path": "test2.py"},
        ],
        "parallel": 2,
    }

    from ollama_coder.batch.job_queue import Job

    job = Job(
        id="test-job",
        type="batch_validation",
        data=job_data,
    )

    # Mock queue
    class MockQueue:
        async def update_job(self, job):
            pass

    queue = MockQueue()

    # Process
    result = await processor.process(job, queue)

    assert "summary" in result
    assert "results" in result
    assert result["summary"]["total"] == 2


@pytest.mark.asyncio
async def test_batch_test_processor():
    """Test batch test processor."""
    processor = BatchTestProcessor()

    # Create mock job
    job_data = {
        "modules": [
            {"id": "test1", "path": "tests/test_config.py"},
        ],
        "test_command": "echo",
        "parallel": 1,
    }

    from ollama_coder.batch.job_queue import Job

    job = Job(
        id="test-job",
        type="batch_tests",
        data=job_data,
    )

    # Mock queue
    class MockQueue:
        async def update_job(self, job):
            pass

    queue = MockQueue()

    # Process
    result = await processor.process(job, queue)

    assert "summary" in result
    assert "results" in result
    assert result["summary"]["total"] == 1


@pytest.mark.asyncio
async def test_batch_mcp_processor_read_operation():
    """Test batch MCP processor with read operations."""
    processor = BatchMCPProcessor()

    # Create a test file
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as f:
        f.write("test content")
        test_file = f.name

    try:
        job_data = {
            "operations": [
                {"type": "read", "path": test_file},
            ],
            "parallel": 1,
        }

        from ollama_coder.batch.job_queue import Job

        job = Job(
            id="test-job",
            type="batch_mcp",
            data=job_data,
        )

        # Mock queue
        class MockQueue:
            async def update_job(self, job):
                pass

        queue = MockQueue()

        # Process
        result = await processor.process(job, queue)

        assert "summary" in result
        assert "results" in result

    finally:
        Path(test_file).unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_job_queue_error_handling(job_queue):
    """Test job queue error handling for failing processors."""

    async def failing_processor(job, queue):
        """Processor that always fails."""
        raise ValueError("Intentional failure")

    # Register failing processor
    job_queue.register_processor("failing", failing_processor)

    # Add job
    job = await job_queue.add_job("failing", {"data": "test"})

    # Wait for processing
    await asyncio.sleep(0.5)

    # Check result
    failed_job = await job_queue.get_job(job.id)
    assert failed_job.status == JobStatus.FAILED
    assert failed_job.error is not None
    assert "Intentional failure" in failed_job.error


@pytest.mark.asyncio
async def test_job_queue_no_processor(job_queue):
    """Test job queue behavior when no processor is registered."""
    # Add job with unregistered type
    job = await job_queue.add_job("unregistered_type", {"data": "test"})

    # Wait for processing
    await asyncio.sleep(0.5)

    # Check result
    processed_job = await job_queue.get_job(job.id)
    assert processed_job.status == JobStatus.FAILED
    assert "No processor registered" in processed_job.error
