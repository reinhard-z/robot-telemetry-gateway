"""Exercise the ROS telemetry pipeline with accelerated timings."""

from __future__ import annotations

import os
import time
import unittest

try:
    from geometry_msgs.msg import PoseStamped

    from launch import LaunchDescription

    from launch_ros.actions import Node as LaunchNode

    import launch_testing
    import launch_testing.actions
    import launch_testing.asserts
    import launch_testing.markers
    from launch_testing.io_handler import ActiveIoHandler
    from launch_testing.proc_info_handler import ProcInfoHandler

    import pytest

    import rclpy
    from rclpy.node import Node as RclpyNode

    from sensor_msgs.msg import BatteryState
except ModuleNotFoundError as error:
    if "ROS_DISTRO" in os.environ:
        raise
    raise unittest.SkipTest("requires a sourced ROS 2 environment") from error


EXPECTED_TRANSITIONS = (
    "position: waiting -> healthy",
    "battery: waiting -> healthy",
    "battery: healthy -> stale",
    "battery: stale -> recovered",
    "position: healthy -> stale",
    "position: stale -> recovered",
)
MINIMUM_SAMPLES_PER_SIGNAL = 3
TOPIC_TIMEOUT_SECONDS = 5.0
TRANSITION_TIMEOUT_SECONDS = 10.0


@pytest.mark.launch_test
@launch_testing.markers.keep_alive
def generate_test_description() -> tuple[
    LaunchDescription,
    dict[str, LaunchNode],
]:
    """Launch both nodes with short, non-overlapping pause windows."""
    simulator = LaunchNode(
        package="robot_telemetry",
        executable="robot_simulator",
        parameters=[
            {
                "publish_rate_hz": 10.0,
                "battery_pause_start_seconds": 1.5,
                "battery_pause_duration_seconds": 1.0,
                "position_pause_start_seconds": 4.0,
                "position_pause_duration_seconds": 1.0,
            }
        ],
    )
    gateway = LaunchNode(
        package="robot_telemetry",
        executable="telemetry_gateway",
        parameters=[
            {
                "position_stale_threshold_seconds": 0.3,
                "battery_stale_threshold_seconds": 0.3,
            }
        ],
    )

    return (
        LaunchDescription(
            [
                simulator,
                gateway,
                launch_testing.actions.ReadyToTest(),
            ]
        ),
        {"gateway": gateway},
    )


class PipelineTest(unittest.TestCase):
    """Verify topic data and gateway transitions across both ROS nodes."""

    @classmethod
    def setUpClass(cls) -> None:
        """Initialize one ROS context for the integration tests."""
        rclpy.init()

    @classmethod
    def tearDownClass(cls) -> None:
        """Shut down the integration test's ROS context."""
        rclpy.shutdown()

    def setUp(self) -> None:
        """Create a temporary node that observes the published topics."""
        self.node: RclpyNode = rclpy.create_node("telemetry_pipeline_test")

    def tearDown(self) -> None:
        """Destroy the temporary test node after each assertion group."""
        self.node.destroy_node()

    def test_both_topics_publish_changing_values(self) -> None:
        """Receive multiple deterministic samples from both publishers."""
        positions: list[PoseStamped] = []
        batteries: list[BatteryState] = []
        position_subscription = self.node.create_subscription(
            PoseStamped,
            "/telemetry/position",
            positions.append,
            10,
        )
        battery_subscription = self.node.create_subscription(
            BatteryState,
            "/telemetry/battery",
            batteries.append,
            10,
        )

        try:
            deadline = time.monotonic() + TOPIC_TIMEOUT_SECONDS
            while time.monotonic() < deadline:
                rclpy.spin_once(self.node, timeout_sec=0.1)
                if (
                    len(positions) >= MINIMUM_SAMPLES_PER_SIGNAL
                    and len(batteries) >= MINIMUM_SAMPLES_PER_SIGNAL
                ):
                    break
        finally:
            self.node.destroy_subscription(position_subscription)
            self.node.destroy_subscription(battery_subscription)

        self.assertGreaterEqual(len(positions), MINIMUM_SAMPLES_PER_SIGNAL)
        self.assertGreaterEqual(len(batteries), MINIMUM_SAMPLES_PER_SIGNAL)
        self.assertGreater(
            positions[-1].pose.position.x,
            positions[0].pose.position.x,
        )
        self.assertLess(batteries[-1].percentage, batteries[0].percentage)

    def test_gateway_logs_each_transition_once(
        self,
        gateway: LaunchNode,
        proc_output: ActiveIoHandler,
    ) -> None:
        """Observe both pause cycles without repeated transition logs."""
        for transition in EXPECTED_TRANSITIONS:
            proc_output.assertWaitFor(
                transition,
                process=gateway,
                timeout=TRANSITION_TIMEOUT_SECONDS,
            )

        output = b"".join(
            event.text for event in proc_output[gateway]
        ).decode(errors="replace")
        for transition in EXPECTED_TRANSITIONS:
            with self.subTest(transition=transition):
                self.assertEqual(output.count(transition), 1)


@launch_testing.post_shutdown_test()
class PipelineShutdownTest(unittest.TestCase):
    """Verify that launch testing can stop both long-running nodes cleanly."""

    def test_processes_exit_cleanly(self, proc_info: ProcInfoHandler) -> None:
        """Require successful exit codes from the simulator and gateway."""
        launch_testing.asserts.assertExitCodes(proc_info)
