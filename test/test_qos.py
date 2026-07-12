"""Verify the ROS telemetry QoS profile."""

from __future__ import annotations

import os
import unittest

try:
    from rclpy.qos import HistoryPolicy, ReliabilityPolicy

    from robot_telemetry.qos import (
        TELEMETRY_QUEUE_DEPTH,
        telemetry_qos_profile,
    )
except ModuleNotFoundError as error:
    if "ROS_DISTRO" in os.environ:
        raise
    raise unittest.SkipTest("requires a sourced ROS 2 environment") from error


class TelemetryQosProfileTest(unittest.TestCase):
    """Keep history and depth fixed while reliability changes."""

    def test_supported_reliability_policies(self) -> None:
        """Map both public configuration values to their ROS policies."""
        expected_policies = {
            "reliable": ReliabilityPolicy.RELIABLE,
            "best_effort": ReliabilityPolicy.BEST_EFFORT,
        }

        for value, expected_policy in expected_policies.items():
            with self.subTest(value=value):
                profile = telemetry_qos_profile(value)

                self.assertEqual(profile.history, HistoryPolicy.KEEP_LAST)
                self.assertEqual(profile.depth, TELEMETRY_QUEUE_DEPTH)
                self.assertEqual(profile.reliability, expected_policy)

    def test_unsupported_reliability_is_rejected(self) -> None:
        """Fail clearly instead of silently selecting another policy."""
        invalid_values = (None, False, 1, "", "RELIABLE", "best-effort")

        for value in invalid_values:
            with self.subTest(value=value):
                with self.assertRaisesRegex(
                    ValueError,
                    "'reliable' or 'best_effort'",
                ):
                    telemetry_qos_profile(value)


if __name__ == "__main__":
    unittest.main()
