"""Receive simulated telemetry and retain each signal's latest data."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from geometry_msgs.msg import PoseStamped

import rclpy
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from rclpy.subscription import Subscription

from robot_telemetry.qos import (
    DEFAULT_QOS_RELIABILITY,
    telemetry_qos_profile,
)
from robot_telemetry.signal_tracker import SignalTracker, SignalTransition
from robot_telemetry.telemetry_values import BatteryValue, PositionValue

from sensor_msgs.msg import BatteryState


POSITION_TOPIC = "/telemetry/position"
BATTERY_TOPIC = "/telemetry/battery"
DEFAULT_STALE_THRESHOLD_SECONDS = 2.5
HEALTH_CHECK_PERIOD_SECONDS = 0.25
NANOSECONDS_PER_MICROSECOND = 1_000

GatewayTracker = (
    SignalTracker[PositionValue] | SignalTracker[BatteryValue]
)


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
        qos_profile = telemetry_qos_profile(
            self.declare_parameter(
                "qos_reliability",
                DEFAULT_QOS_RELIABILITY,
            ).value
        )

        self._position_subscription: Subscription = self.create_subscription(
            PoseStamped,
            POSITION_TOPIC,
            self._record_position,
            qos_profile,
        )
        self._battery_subscription: Subscription = self.create_subscription(
            BatteryState,
            BATTERY_TOPIC,
            self._record_battery,
            qos_profile,
        )
        # Health checks run independently from either message callback.
        self._health_timer = self.create_timer(
            HEALTH_CHECK_PERIOD_SECONDS,
            self._check_signal_health,
        )

    def _record_position(self, message: PoseStamped) -> None:
        """Decode and record one position measurement at the ROS boundary."""
        receipt_time = datetime.now(timezone.utc)
        position = message.pose.position

        transition = self._position_tracker.record_measurement(
            value=PositionValue(x=position.x, y=position.y, z=position.z),
            measurement_time=_message_time(
                seconds=message.header.stamp.sec,
                nanoseconds=message.header.stamp.nanosec,
            ),
            receipt_time=receipt_time,
        )
        self._log_transition(
            "position",
            self._position_tracker,
            transition,
        )

    def _record_battery(self, message: BatteryState) -> None:
        """Decode and record one battery measurement at the ROS boundary."""
        receipt_time = datetime.now(timezone.utc)

        transition = self._battery_tracker.record_measurement(
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
        self._log_transition(
            "battery",
            self._battery_tracker,
            transition,
        )

    def _check_signal_health(self) -> None:
        """Evaluate both trackers on each health-check timer tick."""
        self._log_transition(
            "position",
            self._position_tracker,
            self._position_tracker.check_health(),
        )
        self._log_transition(
            "battery",
            self._battery_tracker,
            self._battery_tracker.check_health(),
        )

    def _log_transition(
        self,
        signal_name: str,
        tracker: GatewayTracker,
        transition: SignalTransition | None,
    ) -> None:
        """Log one health transition and ignore unchanged tracker states."""
        if transition is None:
            return

        if transition is SignalTransition.BECAME_HEALTHY:
            self.get_logger().info(f"{signal_name}: waiting -> healthy")
            return

        if transition is SignalTransition.BECAME_STALE:
            age = tracker.age
            if age is None:
                raise RuntimeError("a stale signal must have a receipt time")

            self.get_logger().warning(
                f"{signal_name}: healthy -> stale "
                f"(age={age:.2f}s, "
                f"threshold={tracker.stale_threshold:.2f}s)"
            )
            return

        if transition is not SignalTransition.RECOVERED:
            raise ValueError(f"unsupported signal transition: {transition}")

        measurement_time = tracker.latest_measurement_time
        receipt_time = tracker.latest_receipt_time
        if measurement_time is None or receipt_time is None:
            raise RuntimeError(
                "a recovered signal must have recorded timestamps"
            )

        self.get_logger().info(
            f"{signal_name}: stale -> recovered "
            f"(measurement_time={measurement_time.isoformat()}, "
            f"receipt_time={receipt_time.isoformat()})"
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
