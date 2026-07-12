"""Represent a deterministic interval when telemetry publishing is paused."""

from __future__ import annotations

import math
from dataclasses import dataclass


def _validate_seconds(name: str, value: object) -> float:
    """Return a non-negative finite duration or timestamp in seconds."""
    error_message = f"{name} must be a non-negative finite number"
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(error_message)
    if not math.isfinite(value) or value < 0:
        raise ValueError(error_message)
    return float(value)


@dataclass(frozen=True)
class PauseWindow:
    """Define one start-inclusive and end-exclusive pause interval."""

    start_seconds: float
    duration_seconds: float

    def __post_init__(self) -> None:
        """Validate and normalize constructor values."""
        start = _validate_seconds("start_seconds", self.start_seconds)
        duration = _validate_seconds("duration_seconds", self.duration_seconds)
        if not math.isfinite(start + duration):
            raise ValueError("pause window end must be finite")

        object.__setattr__(self, "start_seconds", start)
        object.__setattr__(self, "duration_seconds", duration)

    @property
    def end_seconds(self) -> float:
        """Return the first elapsed time after the pause."""
        return self.start_seconds + self.duration_seconds

    def is_active(self, elapsed_seconds: float) -> bool:
        """Return whether elapsed time falls inside the pause interval."""
        elapsed = _validate_seconds("elapsed_seconds", elapsed_seconds)
        return self.start_seconds <= elapsed < self.end_seconds
