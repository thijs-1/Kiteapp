"""Service for managing checkpoint state for resumable ARCO pipeline."""
import json
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import List, Optional
from datetime import datetime


@dataclass
class CheckpointState:
    """State of the ARCO pipeline for checkpoint/restart."""

    completed_periods: List[str] = field(default_factory=list)
    current_period: Optional[str] = None
    cells_extracted: List[int] = field(default_factory=list)
    started_at: Optional[str] = None
    last_updated: Optional[str] = None

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "CheckpointState":
        """Create from dictionary."""
        return cls(
            completed_periods=data.get("completed_periods", []),
            current_period=data.get("current_period"),
            cells_extracted=data.get("cells_extracted", []),
            started_at=data.get("started_at"),
            last_updated=data.get("last_updated"),
        )


class CheckpointService:
    """Manages checkpoint state for resumable pipeline execution."""

    def __init__(self, checkpoint_file: Path):
        """Initialize with path to checkpoint file."""
        self.checkpoint_file = checkpoint_file
        self._state: Optional[CheckpointState] = None

    def load(self) -> CheckpointState:
        """Load checkpoint from disk, or create new state if none exists."""
        if self._state is not None:
            return self._state

        if self.checkpoint_file.exists():
            try:
                with open(self.checkpoint_file, "r") as f:
                    data = json.load(f)
                self._state = CheckpointState.from_dict(data)
                print(f"Loaded checkpoint: {len(self._state.completed_periods)} periods complete")
            except (json.JSONDecodeError, KeyError) as e:
                print(f"Warning: Could not load checkpoint ({e}), starting fresh")
                self._state = CheckpointState(started_at=datetime.now().isoformat())
        else:
            self._state = CheckpointState(started_at=datetime.now().isoformat())

        return self._state

    def save(self) -> None:
        """Atomically save checkpoint to disk (write to temp, then rename)."""
        if self._state is None:
            return

        self._state.last_updated = datetime.now().isoformat()

        # Write to temp file first, then rename for atomicity
        temp_file = self.checkpoint_file.with_suffix(".tmp")
        with open(temp_file, "w") as f:
            json.dump(self._state.to_dict(), f, indent=2)

        # Atomic rename (on Windows, need to remove target first)
        if self.checkpoint_file.exists():
            self.checkpoint_file.unlink()
        temp_file.rename(self.checkpoint_file)

    def is_period_complete(self, period: str) -> bool:
        """Check if a period is already complete."""
        state = self.load()
        return period in state.completed_periods

    def start_period(self, period: str) -> None:
        """Mark a period as in-progress."""
        state = self.load()
        state.current_period = period
        state.cells_extracted = []
        self.save()
        print(f"  Checkpoint: started period {period}")

    def mark_cell_extracted(self, cell_index: int) -> None:
        """Record that a cell has been fully extracted for current period."""
        state = self.load()
        if cell_index not in state.cells_extracted:
            state.cells_extracted.append(cell_index)
            self.save()

    def complete_period(self) -> None:
        """Mark the current period as complete."""
        state = self.load()
        if state.current_period and state.current_period not in state.completed_periods:
            state.completed_periods.append(state.current_period)
        state.current_period = None
        state.cells_extracted = []
        self.save()
        print(f"  Checkpoint: period complete ({len(state.completed_periods)} total)")

    def clear(self) -> None:
        """Remove checkpoint file (for fresh start)."""
        if self.checkpoint_file.exists():
            self.checkpoint_file.unlink()
            print("Checkpoint cleared")
        self._state = None

    def get_progress_summary(self) -> str:
        """Get human-readable progress summary."""
        state = self.load()
        lines = [
            f"Completed periods: {len(state.completed_periods)}",
        ]
        if state.current_period:
            lines.append(f"Current period: {state.current_period}")
            lines.append(f"Cells extracted: {len(state.cells_extracted)}")
        return "\n".join(lines)
