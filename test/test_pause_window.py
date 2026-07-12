import math
import unittest

from robot_telemetry.pause_window import PauseWindow


class PauseWindowTest(unittest.TestCase):
    """Verify pause-window boundaries without ROS or real time."""

    def setUp(self) -> None:
        """Create the default five-second pause window."""
        self.window = PauseWindow(start_seconds=8.0, duration_seconds=5.0)

    def test_time_before_start_is_not_paused(self) -> None:
        """Publishing remains active before the configured start."""
        self.assertFalse(self.window.is_active(7.99))

    def test_start_is_included(self) -> None:
        """The pause begins exactly at its configured start."""
        self.assertTrue(self.window.is_active(8.0))

    def test_time_before_end_is_paused(self) -> None:
        """The pause remains active until its end boundary."""
        self.assertTrue(self.window.is_active(12.99))

    def test_end_is_excluded(self) -> None:
        """Publishing resumes exactly at the end boundary."""
        self.assertEqual(self.window.end_seconds, 13.0)
        self.assertFalse(self.window.is_active(13.0))

    def test_zero_duration_disables_pause(self) -> None:
        """A zero-duration window never pauses publishing."""
        window = PauseWindow(start_seconds=8.0, duration_seconds=0.0)

        self.assertFalse(window.is_active(8.0))

    def test_window_values_must_be_non_negative_and_finite(self) -> None:
        """Invalid start and duration values fail during construction."""
        invalid_values = (False, True, -1.0, math.inf, -math.inf, math.nan)

        for value in invalid_values:
            with self.subTest(start_seconds=value):
                with self.assertRaisesRegex(ValueError, "non-negative finite"):
                    PauseWindow(start_seconds=value, duration_seconds=1.0)
            with self.subTest(duration_seconds=value):
                with self.assertRaisesRegex(ValueError, "non-negative finite"):
                    PauseWindow(start_seconds=1.0, duration_seconds=value)

    def test_window_end_must_be_finite(self) -> None:
        """A finite start and duration must not overflow their sum."""
        with self.assertRaisesRegex(ValueError, "window end must be finite"):
            PauseWindow(start_seconds=1e308, duration_seconds=1e308)

    def test_elapsed_time_must_be_non_negative_and_finite(self) -> None:
        """Invalid elapsed times fail instead of producing a false result."""
        invalid_values = (False, True, -1.0, math.inf, -math.inf, math.nan)

        for value in invalid_values:
            with self.subTest(elapsed_seconds=value):
                with self.assertRaisesRegex(ValueError, "non-negative finite"):
                    self.window.is_active(value)


if __name__ == "__main__":
    unittest.main()
