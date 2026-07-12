"""Track the health of one telemetry signal without ROS dependencies."""

from __future__ import annotations

import math
import time
from collections.abc import Callable
from datetime import datetime
from enum import Enum
from typing import Generic, TypeVar


SignalValue = TypeVar("SignalValue")


class SignalState(Enum):
    """Persistent health states for a telemetry signal."""

    WAITING = "waiting"
    HEALTHY = "healthy"
    STALE = "stale"


class SignalTransition(Enum):
    """State changes that callers may log or otherwise act upon."""

    BECAME_HEALTHY = "became_healthy"
    BECAME_STALE = "became_stale"
    RECOVERED = "recovered"


class SignalTracker(Generic[SignalValue]):
    """Track receipt age and health transitions for one telemetry signal.

    A signal becomes stale when its age is greater than or equal to the
    configured threshold. Recovery is returned as a transition while the
    persistent state immediately becomes healthy again.
    """

    def __init__(
        self,
        stale_threshold: float,
        *,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        """Create a tracker with a positive freshness threshold."""
        if (
            isinstance(stale_threshold, bool)
            or not isinstance(stale_threshold, (int, float))
            or not math.isfinite(stale_threshold)
            or stale_threshold <= 0
        ):
            raise ValueError(
                "stale_threshold must be a positive finite number"
            )

        self._stale_threshold = float(stale_threshold)
        self._clock = clock
        self._state = SignalState.WAITING
        self._latest_measurement_time: datetime | None = None
        self._latest_receipt_time: datetime | None = None
        self._latest_receipt_monotonic: float | None = None
        self._latest_value: SignalValue | None = None
        self._last_clock_reading: float | None = None

    @property
    def state(self) -> SignalState:
        """Return the current persistent health state."""
        return self._state

    @property
    def stale_threshold(self) -> float:
        """Return the immutable stale threshold in seconds."""
        return self._stale_threshold

    @property
    def latest_measurement_time(self) -> datetime | None:
        """Return the source timestamp of the latest measurement."""
        return self._latest_measurement_time

    @property
    def latest_receipt_time(self) -> datetime | None:
        """Return the wall-clock time when the latest measurement arrived."""
        return self._latest_receipt_time

    @property
    def latest_value(self) -> SignalValue | None:
        """Return the latest decoded value, or ``None`` while waiting."""
        return self._latest_value

    @property
    def age(self) -> float | None:
        """Return seconds since receipt, or ``None`` while waiting."""
        if self._latest_receipt_monotonic is None:
            return None

        return self._read_clock() - self._latest_receipt_monotonic

    def record_measurement(
        self,
        *,
        value: SignalValue,
        measurement_time: datetime,
        receipt_time: datetime,
    ) -> SignalTransition | None:
        """Record an arrival and report a health transition if one occurs."""
        receipt_monotonic = self._read_clock()
        previous_state = self._state

        self._latest_measurement_time = measurement_time
        self._latest_receipt_time = receipt_time
        self._latest_receipt_monotonic = receipt_monotonic
        self._latest_value = value
        self._state = SignalState.HEALTHY

        if previous_state is SignalState.WAITING:
            return SignalTransition.BECAME_HEALTHY
        if previous_state is SignalState.STALE:
            return SignalTransition.RECOVERED
        return None

    def check_health(self) -> SignalTransition | None:
        """Evaluate staleness and return a transition when health changes."""
        if self._state is not SignalState.HEALTHY:
            return None

        age = self.age
        if age is not None and age >= self.stale_threshold:
            self._state = SignalState.STALE
            return SignalTransition.BECAME_STALE
        return None

    def _read_clock(self) -> float:
        """Read and validate the clock used for elapsed-time decisions."""
        reading = self._clock()
        if (
            isinstance(reading, bool)
            or not isinstance(reading, (int, float))
            or not math.isfinite(reading)
        ):
            raise ValueError("clock must return a finite number")

        current_time = float(reading)
        if (
            self._last_clock_reading is not None
            and current_time < self._last_clock_reading
        ):
            raise ValueError("clock must not move backwards")

        self._last_clock_reading = current_time
        return current_time
