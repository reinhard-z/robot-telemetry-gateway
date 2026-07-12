"""Receive simulated telemetry and retain each signal's latest data."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from geometry_msgs.msg import PoseStamped

import rclpy
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from rclpy.subscription import Subscription

from robot_telemetry.signal_tracker import SignalTracker
from robot_telemetry.telemetry_values import BatteryValue, PositionValue

from sensor_msgs.msg import BatteryState


POSITION_TOPIC = "/telemetry/position"
BATTERY_TOPIC = "/telemetry/battery"
DEFAULT_STALE_THRESHOLD_SECONDS = 2.5
SUBSCRIPTION_QUEUE_DEPTH = 10
NANOSECONDS_PER_MICROSECOND = 1_000


def _message_time(*, seconds: int, nanoseconds: int) -> datetime:
    """Convert a ROS header timestamp to a timezone-aware UTC datetime."""
    timestamp = datetime.fromtimestamp(seconds, tz=timezone.utc)
    # datetime stores microseconds, so sub-microsecond precision is discarded.
    return timestamp + timedelta(
        microseconds=nanoseconds // NANOSECONDS_PER_MICROSECOND
    )


class TelemetryGateway(Node):
    """Subscribe to position and battery telemetry and track their arrivals."""

    def __init__(self) -> None:
        """Create independent trackers and subscriptions for both signals."""
        super().__init__("telemetry_gateway")

        position_stale_threshold = self.declare_parameter(
            "position_stale_threshold_seconds",
            DEFAULT_STALE_THRESHOLD_SECONDS,
        ).value
        battery_stale_threshold = self.declare_parameter(
            "battery_stale_threshold_seconds",
            DEFAULT_STALE_THRESHOLD_SECONDS,
        ).value

        self._position_tracker = SignalTracker[PositionValue](
            stale_threshold=position_stale_threshold,
        )
        self._battery_tracker = SignalTracker[BatteryValue](
            stale_threshold=battery_stale_threshold,
        )

        self._position_subscription: Subscription = self.create_subscription(
            PoseStamped,
            POSITION_TOPIC,
            self._record_position,
            SUBSCRIPTION_QUEUE_DEPTH,
        )
        self._battery_subscription: Subscription = self.create_subscription(
            BatteryState,
            BATTERY_TOPIC,
            self._record_battery,
            SUBSCRIPTION_QUEUE_DEPTH,
        )

    def _record_position(self, message: PoseStamped) -> None:
        """Decode and record one position measurement at the ROS boundary."""
        receipt_time = datetime.now(timezone.utc)
        position = message.pose.position

        self._position_tracker.record_measurement(
            value=PositionValue(x=position.x, y=position.y, z=position.z),
            measurement_time=_message_time(
                seconds=message.header.stamp.sec,
                nanoseconds=message.header.stamp.nanosec,
            ),
            receipt_time=receipt_time,
        )

    def _record_battery(self, message: BatteryState) -> None:
        """Decode and record one battery measurement at the ROS boundary."""
        receipt_time = datetime.now(timezone.utc)

        self._battery_tracker.record_measurement(
            value=BatteryValue(
                percentage=message.percentage,
                voltage=message.voltage,
                charge=message.charge,
            ),
            measurement_time=_message_time(
                seconds=message.header.stamp.sec,
                nanoseconds=message.header.stamp.nanosec,
            ),
            receipt_time=receipt_time,
        )


def main(args: list[str] | None = None) -> None:
    """Run the gateway until ROS shuts down or the user interrupts it."""
    rclpy.init(args=args)
    node: TelemetryGateway | None = None

    try:
        node = TelemetryGateway()
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        if node is not None:
            node.destroy_node()
        rclpy.try_shutdown()


if __name__ == "__main__":
    main()
