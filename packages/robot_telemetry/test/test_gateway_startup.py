"""Verify that invalid C++ gateway configuration fails clearly."""

from __future__ import annotations

import os
import unittest

try:
    from launch import LaunchDescription
    from launch_ros.actions import Node as LaunchNode

    import launch_testing
    import launch_testing.actions
    from launch_testing.io_handler import ActiveIoHandler
    from launch_testing.proc_info_handler import ProcInfoHandler

    import pytest
except ImportError as error:
    if "ROS_DISTRO" in os.environ:
        raise
    raise unittest.SkipTest("requires a sourced ROS 2 environment") from error


INVALID_CASES = {
    "threshold": (
        {"position_stale_threshold_seconds": 0.0},
        "position_stale_threshold_seconds must be a positive finite number",
    ),
    "qos": (
        {"qos_reliability": "invalid"},
        "qos_reliability must be 'reliable' or 'best_effort'",
    ),
}


@pytest.mark.launch_test
def generate_test_description() -> tuple[LaunchDescription, dict[str, object]]:
    """Start one gateway process for each invalid parameter category."""
    gateways: dict[str, LaunchNode] = {}
    diagnostics: dict[str, str] = {}

    for name, (parameters, diagnostic) in INVALID_CASES.items():
        gateways[name] = LaunchNode(
            package="robot_telemetry_gateway",
            executable="telemetry_gateway",
            name=f"invalid_{name}_gateway",
            parameters=[parameters],
        )
        diagnostics[name] = diagnostic

    return (
        LaunchDescription(
            [*gateways.values(), launch_testing.actions.ReadyToTest()]
        ),
        {"invalid_gateways": gateways, "diagnostics": diagnostics},
    )


class GatewayStartupTest(unittest.TestCase):
    """Require a useful diagnostic from each invalid gateway process."""

    def test_invalid_configuration_is_rejected(
        self,
        invalid_gateways: dict[str, LaunchNode],
        diagnostics: dict[str, str],
        proc_output: ActiveIoHandler,
    ) -> None:
        """Wait for each expected validation message."""
        for name, gateway in invalid_gateways.items():
            with self.subTest(case=name):
                proc_output.assertWaitFor(
                    diagnostics[name],
                    process=gateway,
                    timeout=5.0,
                )


@launch_testing.post_shutdown_test()
class GatewayStartupExitTest(unittest.TestCase):
    """Require invalid gateway processes to return a failure code."""

    def test_invalid_processes_exit_nonzero(
        self,
        invalid_gateways: dict[str, LaunchNode],
        proc_info: ProcInfoHandler,
    ) -> None:
        """Reject accidental successful startup for every invalid case."""
        for name, gateway in invalid_gateways.items():
            with self.subTest(case=name):
                self.assertNotEqual(proc_info[gateway].returncode, 0)
