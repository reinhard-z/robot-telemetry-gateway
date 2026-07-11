"""Publish deterministic robot telemetry for the local ROS 2 demonstration."""

from __future__ import annotations

import math

from geometry_msgs.msg import PoseStamped

import rclpy
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from rclpy.publisher import Publisher


POSITION_TOPIC = "/telemetry/position"
POSITION_FRAME_ID = "map"
DEFAULT_PUBLISH_RATE_HZ = 1.0
POSITION_STEP_METERS = 0.25


def _validate_publish_rate(value: object) -> float:
    """Return a positive finite publishing rate in hertz."""
    error_message = "publish_rate_hz must be a positive finite number"
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(error_message)
    if not math.isfinite(value) or value <= 0:
        raise ValueError(error_message)
    return float(value)


class RobotSimulator(Node):
    """Publish a deterministic position moving along the positive x-axis."""

    def __init__(self) -> None:
        """Create the position publisher and its configurable timer."""
        super().__init__("robot_simulator")

        publish_rate = _validate_publish_rate(
            self.declare_parameter(
                "publish_rate_hz",
                DEFAULT_PUBLISH_RATE_HZ,
            ).value
        )

        self._position_publisher: Publisher = self.create_publisher(
            PoseStamped,
            POSITION_TOPIC,
            10,
        )
        self._sample_index = 0
        self._timer = self.create_timer(
            1.0 / publish_rate,
            self._publish_position,
        )

    def _publish_position(self) -> None:
        """Publish the next sample on the simulator's straight-line path."""
        message = PoseStamped()
        message.header.stamp = self.get_clock().now().to_msg()
        message.header.frame_id = POSITION_FRAME_ID
        message.pose.position.x = self._sample_index * POSITION_STEP_METERS
        message.pose.orientation.w = 1.0

        self._position_publisher.publish(message)
        self._sample_index += 1


def main(args: list[str] | None = None) -> None:
    """Run the simulator until ROS shuts down or the user interrupts it."""
    rclpy.init(args=args)
    node: RobotSimulator | None = None

    try:
        node = RobotSimulator()
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        if node is not None:
            node.destroy_node()
        rclpy.try_shutdown()


if __name__ == "__main__":
    main()
