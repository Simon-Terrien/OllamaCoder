"""Lightweight async job queue with SQLite persistence for batch processing."""

from __future__ import annotations

import asyncio
import json
import sqlite3
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional


class JobStatus(str, Enum):
    """Job status enumeration."""

    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class Job:
    """Represents a batch processing job."""

    id: str
    type: str
    data: Dict[str, Any]
    status: JobStatus = JobStatus.QUEUED
    progress: float = 0.0
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert job to dictionary."""
        return {
            "id": self.id,
            "type": self.type,
            "data": self.data,
            "status": self.status.value,
            "progress": self.progress,
            "result": self.result,
            "error": self.error,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Job:
        """Create job from dictionary."""
        return cls(
            id=data["id"],
            type=data["type"],
            data=data["data"],
            status=JobStatus(data["status"]),
            progress=data.get("progress", 0.0),
            result=data.get("result"),
            error=data.get("error"),
            created_at=data.get("created_at", time.time()),
            started_at=data.get("started_at"),
            completed_at=data.get("completed_at"),
            metadata=data.get("metadata", {}),
        )


class JobQueue:
    """Async job queue with SQLite persistence and parallel processing."""

    def __init__(
        self,
        db_path: str | Path = "data/batch_jobs.db",
        max_workers: int = 5,
        chunk_size: int = 100,
    ):
        """Initialize job queue.

        Args:
            db_path: Path to SQLite database
            max_workers: Maximum concurrent workers
            chunk_size: Batch size for processing
        """
        self.db_path = Path(db_path)
        self.max_workers = max_workers
        self.chunk_size = chunk_size
        self.processors: Dict[str, Callable] = {}
        self._running = False
        self._worker_tasks: List[asyncio.Task] = []
        self._init_db()

    def _init_db(self) -> None:
        """Initialize SQLite database."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY,
                type TEXT NOT NULL,
                data TEXT NOT NULL,
                status TEXT NOT NULL,
                progress REAL DEFAULT 0.0,
                result TEXT,
                error TEXT,
                created_at REAL NOT NULL,
                started_at REAL,
                completed_at REAL,
                metadata TEXT
            )
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_status ON jobs(status)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_type ON jobs(type)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_created_at ON jobs(created_at)
        """)

        conn.commit()
        conn.close()

    def register_processor(self, job_type: str, processor: Callable) -> None:
        """Register a processor function for a job type.

        Args:
            job_type: Type of job to process
            processor: Async function that processes the job
        """
        self.processors[job_type] = processor

    async def add_job(
        self,
        job_type: str,
        data: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Job:
        """Add a new job to the queue.

        Args:
            job_type: Type of job
            data: Job data
            metadata: Optional metadata

        Returns:
            Created job
        """
        job = Job(
            id=f"{job_type}-{uuid.uuid4().hex[:12]}",
            type=job_type,
            data=data,
            metadata=metadata or {},
        )

        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO jobs (id, type, data, status, progress, created_at, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
            (
                job.id,
                job.type,
                json.dumps(job.data),
                job.status.value,
                job.progress,
                job.created_at,
                json.dumps(job.metadata),
            ),
        )

        conn.commit()
        conn.close()

        return job

    async def get_job(self, job_id: str) -> Optional[Job]:
        """Get job by ID.

        Args:
            job_id: Job ID

        Returns:
            Job or None if not found
        """
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM jobs WHERE id = ?", (job_id,))
        row = cursor.fetchone()
        conn.close()

        if not row:
            return None

        return Job.from_dict(
            {
                "id": row[0],
                "type": row[1],
                "data": json.loads(row[2]),
                "status": row[3],
                "progress": row[4],
                "result": json.loads(row[5]) if row[5] else None,
                "error": row[6],
                "created_at": row[7],
                "started_at": row[8],
                "completed_at": row[9],
                "metadata": json.loads(row[10]) if row[10] else {},
            }
        )

    async def update_job(self, job: Job) -> None:
        """Update job in database.

        Args:
            job: Job to update
        """
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        cursor.execute(
            """
            UPDATE jobs
            SET status = ?, progress = ?, result = ?, error = ?,
                started_at = ?, completed_at = ?, metadata = ?
            WHERE id = ?
        """,
            (
                job.status.value,
                job.progress,
                json.dumps(job.result) if job.result else None,
                job.error,
                job.started_at,
                job.completed_at,
                json.dumps(job.metadata),
                job.id,
            ),
        )

        conn.commit()
        conn.close()

    async def list_jobs(
        self,
        status: Optional[JobStatus] = None,
        job_type: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Job]:
        """List jobs with optional filtering.

        Args:
            status: Filter by status
            job_type: Filter by type
            limit: Maximum results
            offset: Result offset

        Returns:
            List of jobs
        """
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        query = "SELECT * FROM jobs WHERE 1=1"
        params: List[Any] = []

        if status:
            query += " AND status = ?"
            params.append(status.value)

        if job_type:
            query += " AND type = ?"
            params.append(job_type)

        query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()

        jobs = []
        for row in rows:
            jobs.append(
                Job.from_dict(
                    {
                        "id": row[0],
                        "type": row[1],
                        "data": json.loads(row[2]),
                        "status": row[3],
                        "progress": row[4],
                        "result": json.loads(row[5]) if row[5] else None,
                        "error": row[6],
                        "created_at": row[7],
                        "started_at": row[8],
                        "completed_at": row[9],
                        "metadata": json.loads(row[10]) if row[10] else {},
                    }
                )
            )

        return jobs

    async def _get_next_job(self) -> Optional[Job]:
        """Get next queued job."""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        # Atomic claim: set to RUNNING and return
        cursor.execute(
            """
            UPDATE jobs
            SET status = ?, started_at = ?
            WHERE id = (
                SELECT id FROM jobs
                WHERE status = ?
                ORDER BY created_at ASC
                LIMIT 1
            )
            RETURNING *
        """,
            (JobStatus.RUNNING.value, time.time(), JobStatus.QUEUED.value),
        )

        row = cursor.fetchone()
        conn.commit()
        conn.close()

        if not row:
            return None

        return Job.from_dict(
            {
                "id": row[0],
                "type": row[1],
                "data": json.loads(row[2]),
                "status": row[3],
                "progress": row[4],
                "result": json.loads(row[5]) if row[5] else None,
                "error": row[6],
                "created_at": row[7],
                "started_at": row[8],
                "completed_at": row[9],
                "metadata": json.loads(row[10]) if row[10] else {},
            }
        )

    async def _worker(self, worker_id: int) -> None:
        """Worker coroutine that processes jobs.

        Args:
            worker_id: Worker identifier
        """
        while self._running:
            try:
                job = await self._get_next_job()

                if not job:
                    # No jobs available, sleep briefly
                    await asyncio.sleep(0.5)
                    continue

                processor = self.processors.get(job.type)

                if not processor:
                    job.status = JobStatus.FAILED
                    job.error = f"No processor registered for job type: {job.type}"
                    job.completed_at = time.time()
                    await self.update_job(job)
                    continue

                # Process job
                try:
                    result = await processor(job, self)
                    job.status = JobStatus.COMPLETED
                    job.result = result
                    job.progress = 100.0
                    job.completed_at = time.time()
                except Exception as e:
                    job.status = JobStatus.FAILED
                    job.error = str(e)
                    job.completed_at = time.time()

                await self.update_job(job)

            except Exception as e:
                print(f"Worker {worker_id} error: {e}")
                await asyncio.sleep(1)

    async def start(self) -> None:
        """Start the job queue workers."""
        if self._running:
            return

        self._running = True

        # Start worker tasks
        for i in range(self.max_workers):
            task = asyncio.create_task(self._worker(i))
            self._worker_tasks.append(task)

        print(f"✅ Job queue started with {self.max_workers} workers")

    async def stop(self) -> None:
        """Stop the job queue workers."""
        self._running = False

        # Wait for workers to finish
        if self._worker_tasks:
            await asyncio.gather(*self._worker_tasks, return_exceptions=True)
            self._worker_tasks.clear()

        print("✅ Job queue stopped")

    async def cancel_job(self, job_id: str) -> bool:
        """Cancel a job.

        Args:
            job_id: Job ID

        Returns:
            True if cancelled, False otherwise
        """
        job = await self.get_job(job_id)

        if not job or job.status not in [JobStatus.QUEUED, JobStatus.RUNNING]:
            return False

        job.status = JobStatus.CANCELLED
        job.completed_at = time.time()
        await self.update_job(job)

        return True

    async def get_stats(self) -> Dict[str, Any]:
        """Get queue statistics.

        Returns:
            Statistics dictionary
        """
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT status, COUNT(*) as count
            FROM jobs
            GROUP BY status
        """
        )

        stats = {"total": 0}
        for row in cursor.fetchall():
            status = row[0]
            count = row[1]
            stats[status] = count
            stats["total"] += count

        conn.close()

        return stats
