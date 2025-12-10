"""Progress tracking for batch operations."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class ProgressTracker:
    """Tracks progress of batch operations."""

    total: int
    processed: int = 0
    successful: int = 0
    failed: int = 0
    skipped: int = 0
    started_at: float = field(default_factory=time.time)
    current_item: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def percentage(self) -> float:
        """Calculate completion percentage."""
        if self.total == 0:
            return 100.0
        return min(100.0, (self.processed / self.total) * 100.0)

    @property
    def elapsed_seconds(self) -> float:
        """Calculate elapsed time in seconds."""
        return time.time() - self.started_at

    @property
    def items_per_second(self) -> float:
        """Calculate processing rate."""
        elapsed = self.elapsed_seconds
        if elapsed == 0:
            return 0.0
        return self.processed / elapsed

    @property
    def estimated_remaining_seconds(self) -> float:
        """Estimate remaining time in seconds."""
        if self.processed == 0:
            return 0.0
        rate = self.items_per_second
        if rate == 0:
            return 0.0
        remaining = self.total - self.processed
        return remaining / rate

    def increment(
        self,
        success: bool = True,
        skip: bool = False,
        current_item: Optional[str] = None,
    ) -> None:
        """Increment progress counters.

        Args:
            success: Whether item was successful
            skip: Whether item was skipped
            current_item: Current item being processed
        """
        self.processed += 1

        if skip:
            self.skipped += 1
        elif success:
            self.successful += 1
        else:
            self.failed += 1

        if current_item:
            self.current_item = current_item

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "total": self.total,
            "processed": self.processed,
            "successful": self.successful,
            "failed": self.failed,
            "skipped": self.skipped,
            "percentage": round(self.percentage, 2),
            "elapsed_seconds": round(self.elapsed_seconds, 2),
            "items_per_second": round(self.items_per_second, 2),
            "estimated_remaining_seconds": round(self.estimated_remaining_seconds, 2),
            "current_item": self.current_item,
            "metadata": self.metadata,
        }

    def __repr__(self) -> str:
        """String representation of progress."""
        return (
            f"Progress({self.processed}/{self.total} = {self.percentage:.1f}%, "
            f"✓{self.successful} ✗{self.failed} ⊘{self.skipped}, "
            f"{self.items_per_second:.1f} items/s)"
        )
