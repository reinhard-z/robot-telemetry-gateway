"""Launch-test contract for the production telemetry pipeline."""

from __future__ import annotations

from dataclasses import dataclass
import time

from geometry_msgs.msg import PoseStamped
from launch import LaunchDescription
from launch_ros.actions import Node as LaunchNode
import launch_testing
import launch_testing.actions
import launch_testing.asserts
from launch_testing.io_handler import ActiveIoHandler
from launch_testing.proc_info_handler import ProcInfoHandler
import rclpy
from rclpy.node import Node as RclpyNode

from robot_telemetry.qos import telemetry_qos_profile

from sensor_msgs.msg import BatteryState


# Compare stable transition text; client libraries format prefixes and
# recovery timestamp precision differently.
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


@dataclass(frozen=True)
class QosPairing:
    """Describe one publisher/subscriber reliability combination."""

    name: str
    publisher_reliability: str
    gateway_reliability: str
    expects_gateway_data: bool


# Reliable subscribers cannot match best-effort publishers. The other three
# reliability combinations are compatible under the ROS 2 request/offered model.
QOS_PAIRINGS = (
    QosPairing("reliable_to_reliable", "reliable", "reliable", True),
    QosPairing("reliable_to_best_effort", "reliable", "best_effort", True),
    QosPairing("best_effort_to_best_effort", "best_effort", "best_effort", True),
    QosPairing("best_effort_to_reliable", "best_effort", "reliable", False),
)


def build_pipeline_test_description() -> tuple[
    LaunchDescription, dict[str, object]
]:
    """Launch one isolated simulator/gateway pair for each QoS combination."""
    actions: list[object] = []
    gateways: dict[str, LaunchNode] = {}

    for pairing in QOS_PAIRINGS:
        topic_root = f"/pipeline/{pairing.name}"
        remappings = [
            ("/telemetry/position", f"{topic_root}/position"),
            ("/telemetry/battery", f"{topic_root}/battery"),
        ]
        simulator = LaunchNode(
            package="robot_telemetry",
            executable="robot_simulator",
            name=f"simulator_{pairing.name}",
            parameters=[
                {
                    "publish_rate_hz": 10.0,
                    "battery_pause_start_seconds": 1.5,
                    "battery_pause_duration_seconds": 1.0,
                    "position_pause_start_seconds": 4.0,
                    "position_pause_duration_seconds": 1.0,
                    "qos_reliability": pairing.publisher_reliability,
                }
            ],
            remappings=remappings,
        )
        gateway = LaunchNode(
            package="robot_telemetry_gateway",
            executable="telemetry_gateway",
            name=f"gateway_{pairing.name}",
            parameters=[
                {
                    "position_stale_threshold_seconds": 0.3,
                    "battery_stale_threshold_seconds": 0.3,
                    "qos_reliability": pairing.gateway_reliability,
                }
            ],
            remappings=remappings,
        )

        actions.extend((simulator, gateway))
        gateways[pairing.name] = gateway

    actions.append(launch_testing.actions.ReadyToTest())
    return (
        LaunchDescription(actions),
        {"gateways": gateways, "pairings": QOS_PAIRINGS},
    )


class PipelineContractMixin:
    """Verify the observable behavior of the production pipeline."""

    @classmethod
    def setUpClass(cls) -> None:
        """Initialize one ROS context for this launch-test module."""
        rclpy.init()

    @classmethod
    def tearDownClass(cls) -> None:
        """Shut down the launch-test ROS context."""
        rclpy.shutdown()

    def setUp(self) -> None:
        """Create a temporary observer node for topic assertions."""
        self.node: RclpyNode = rclpy.create_node("telemetry_pipeline_test")

    def tearDown(self) -> None:
        """Destroy the observer node after each assertion group."""
        self.node.destroy_node()

    def test_all_pairings_publish_changing_values(
        self,
        pairings: tuple[QosPairing, ...],
    ) -> None:
        """Inspect changing source data for every live QoS pairing."""
        positions: dict[str, list[PoseStamped]] = {
            pairing.name: [] for pairing in pairings
        }
        batteries: dict[str, list[BatteryState]] = {
            pairing.name: [] for pairing in pairings
        }
        subscriptions = []
        observer_qos = telemetry_qos_profile("best_effort")

        for pairing in pairings:
            topic_root = f"/pipeline/{pairing.name}"
            subscriptions.extend(
                (
                    self.node.create_subscription(
                        PoseStamped,
                        f"{topic_root}/position",
                        positions[pairing.name].append,
                        observer_qos,
                    ),
                    self.node.create_subscription(
                        BatteryState,
                        f"{topic_root}/battery",
                        batteries[pairing.name].append,
                        observer_qos,
                    ),
                )
            )

        try:
            deadline = time.monotonic() + TOPIC_TIMEOUT_SECONDS
            while time.monotonic() < deadline:
                rclpy.spin_once(self.node, timeout_sec=0.1)
                if all(
                    len(positions[pairing.name]) >= MINIMUM_SAMPLES_PER_SIGNAL
                    and len(batteries[pairing.name])
                    >= MINIMUM_SAMPLES_PER_SIGNAL
                    for pairing in pairings
                ):
                    break
        finally:
            for subscription in subscriptions:
                self.node.destroy_subscription(subscription)

        for pairing in pairings:
            with self.subTest(pairing=pairing.name):
                pairing_positions = positions[pairing.name]
                pairing_batteries = batteries[pairing.name]
                self.assertGreaterEqual(
                    len(pairing_positions), MINIMUM_SAMPLES_PER_SIGNAL
                )
                self.assertGreaterEqual(
                    len(pairing_batteries), MINIMUM_SAMPLES_PER_SIGNAL
                )
                self.assertGreater(
                    pairing_positions[-1].pose.position.x,
                    pairing_positions[0].pose.position.x,
                )
                self.assertLess(
                    pairing_batteries[-1].percentage,
                    pairing_batteries[0].percentage,
                )

    def test_gateway_transitions_match_qos_compatibility(
        self,
        gateways: dict[str, LaunchNode],
        pairings: tuple[QosPairing, ...],
        proc_output: ActiveIoHandler,
    ) -> None:
        """Require transitions only for QoS-compatible gateway pairings."""
        for pairing in pairings:
            if not pairing.expects_gateway_data:
                continue
            for transition in EXPECTED_TRANSITIONS:
                proc_output.assertWaitFor(
                    transition,
                    process=gateways[pairing.name],
                    timeout=TRANSITION_TIMEOUT_SECONDS,
                )

        for pairing in pairings:
            output = b"".join(
                event.text for event in proc_output[gateways[pairing.name]]
            ).decode(errors="replace")
            expected_count = 1 if pairing.expects_gateway_data else 0

            for transition in EXPECTED_TRANSITIONS:
                with self.subTest(
                    pairing=pairing.name,
                    transition=transition,
                ):
                    self.assertEqual(output.count(transition), expected_count)

            with self.subTest(pairing=pairing.name, transition="healthy"):
                self.assertEqual(
                    output.count("waiting -> healthy"),
                    expected_count * 2,
                )
            with self.subTest(pairing=pairing.name, transition="stale"):
                self.assertEqual(
                    output.count("healthy -> stale"),
                    expected_count * 2,
                )
            with self.subTest(pairing=pairing.name, transition="recovered"):
                self.assertEqual(
                    output.count("stale -> recovered"),
                    expected_count * 2,
                )


class PipelineShutdownMixin:
    """Require all simulator and gateway processes to stop cleanly."""

    def test_processes_exit_cleanly(self, proc_info: ProcInfoHandler) -> None:
        """Accept only successful process exit codes."""
        launch_testing.asserts.assertExitCodes(proc_info)
