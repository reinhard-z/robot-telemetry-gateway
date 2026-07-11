from __future__ import annotations

import math
import unittest
from datetime import datetime, timedelta, timezone

from robot_telemetry.signal_tracker import (
    SignalState,
    SignalTracker,
    SignalTransition,
)


class FakeClock:
    """Provide a controllable monotonic clock for deterministic tests."""

    def __init__(self, initial_time: float = 0.0) -> None:
        self.current_time = initial_time

    def __call__(self) -> float:
        return self.current_time

    def advance(self, seconds: float) -> None:
        self.current_time += seconds


class SignalTrackerTest(unittest.TestCase):
    """Verify signal state and transition behavior without ROS or real time."""

    def setUp(self) -> None:
        self.clock = FakeClock(initial_time=100.0)
        self.tracker = SignalTracker(stale_threshold=2.5, clock=self.clock)
        self.measurement_time = datetime(2026, 7, 11, 10, 0, tzinfo=timezone.utc)
        self.receipt_time = self.measurement_time + timedelta(milliseconds=50)

    def record_measurement(
        self,
        *,
        measurement_time: datetime | None = None,
        receipt_time: datetime | None = None,
    ) -> SignalTransition | None:
        """Record a measurement using the test's default timestamps."""
        return self.tracker.record_measurement(
            measurement_time=measurement_time or self.measurement_time,
            receipt_time=receipt_time or self.receipt_time,
        )

    def test_signal_is_waiting_before_any_measurement(self) -> None:
        self.assertEqual(self.tracker.state, SignalState.WAITING)
        self.assertIsNone(self.tracker.latest_measurement_time)
        self.assertIsNone(self.tracker.latest_receipt_time)
        self.assertIsNone(self.tracker.age)
        self.assertIsNone(self.tracker.check_health())

    def test_first_measurement_becomes_healthy_and_records_timestamps(self) -> None:
        transition = self.record_measurement()

        self.assertEqual(transition, SignalTransition.BECAME_HEALTHY)
        self.assertEqual(self.tracker.state, SignalState.HEALTHY)
        self.assertEqual(
            self.tracker.latest_measurement_time,
            self.measurement_time,
        )
        self.assertEqual(self.tracker.latest_receipt_time, self.receipt_time)
        self.assertEqual(self.tracker.age, 0.0)

    def test_age_below_threshold_remains_healthy(self) -> None:
        self.record_measurement()
        self.clock.advance(2.49)

        self.assertAlmostEqual(self.tracker.age, 2.49)
        self.assertIsNone(self.tracker.check_health())
        self.assertEqual(self.tracker.state, SignalState.HEALTHY)

    def test_age_exactly_at_threshold_becomes_stale(self) -> None:
        self.record_measurement()
        self.clock.advance(2.5)

        self.assertEqual(
            self.tracker.check_health(),
            SignalTransition.BECAME_STALE,
        )
        self.assertEqual(self.tracker.state, SignalState.STALE)

    def test_healthy_signal_becomes_stale_above_threshold(self) -> None:
        self.record_measurement()
        self.clock.advance(3.0)

        self.assertEqual(
            self.tracker.check_health(),
            SignalTransition.BECAME_STALE,
        )
        self.assertEqual(self.tracker.state, SignalState.STALE)

    def test_new_measurement_while_healthy_resets_age_without_transition(self) -> None:
        self.record_measurement()
        self.clock.advance(2.0)
        next_measurement_time = self.measurement_time + timedelta(seconds=2)
        next_receipt_time = self.receipt_time + timedelta(seconds=2)

        transition = self.record_measurement(
            measurement_time=next_measurement_time,
            receipt_time=next_receipt_time,
        )

        self.assertIsNone(transition)
        self.assertEqual(self.tracker.state, SignalState.HEALTHY)
        self.assertEqual(self.tracker.latest_measurement_time, next_measurement_time)
        self.assertEqual(self.tracker.latest_receipt_time, next_receipt_time)
        self.assertEqual(self.tracker.age, 0.0)

    def test_new_measurement_after_stale_reports_recovery(self) -> None:
        self.record_measurement()
        self.clock.advance(2.5)
        self.tracker.check_health()

        transition = self.record_measurement()

        self.assertEqual(transition, SignalTransition.RECOVERED)
        self.assertEqual(self.tracker.state, SignalState.HEALTHY)
        self.assertNotIn("recovered", {state.value for state in SignalState})

    def test_unchanged_states_do_not_repeat_transitions(self) -> None:
        self.assertIsNone(self.tracker.check_health())
        self.record_measurement()
        self.assertIsNone(self.record_measurement())

        self.clock.advance(2.5)
        self.assertEqual(
            self.tracker.check_health(),
            SignalTransition.BECAME_STALE,
        )
        self.assertIsNone(self.tracker.check_health())

    def test_stale_threshold_must_be_positive_and_finite(self) -> None:
        invalid_thresholds = (False, True, 0.0, -1.0, math.inf, -math.inf, math.nan)

        for threshold in invalid_thresholds:
            with self.subTest(threshold=threshold):
                with self.assertRaisesRegex(ValueError, "positive finite"):
                    SignalTracker(stale_threshold=threshold)

    def test_clock_must_return_a_finite_number(self) -> None:
        tracker = SignalTracker(stale_threshold=2.5, clock=lambda: math.nan)

        with self.assertRaisesRegex(ValueError, "finite number"):
            tracker.record_measurement(
                measurement_time=self.measurement_time,
                receipt_time=self.receipt_time,
            )

    def test_clock_must_not_move_backwards(self) -> None:
        self.record_measurement()
        self.clock.current_time -= 1.0

        with self.assertRaisesRegex(ValueError, "must not move backwards"):
            _ = self.tracker.age


if __name__ == "__main__":
    unittest.main()
