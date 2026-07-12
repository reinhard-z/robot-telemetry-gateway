"""Publish deterministic robot telemetry for the local ROS 2 demonstration."""

from __future__ import annotations

import math

from geometry_msgs.msg import PoseStamped

import rclpy
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from rclpy.publisher import Publisher

from robot_telemetry.pause_window import PauseWindow

from sensor_msgs.msg import BatteryState


POSITION_TOPIC = "/telemetry/position"
POSITION_FRAME_ID = "map"
BATTERY_TOPIC = "/telemetry/battery"
BATTERY_FRAME_ID = "base_link"
DEFAULT_PUBLISH_RATE_HZ = 1.0
DEFAULT_BATTERY_PAUSE_START_SECONDS = 8.0
DEFAULT_BATTERY_PAUSE_DURATION_SECONDS = 5.0
DEFAULT_POSITION_PAUSE_START_SECONDS = 21.0
DEFAULT_POSITION_PAUSE_DURATION_SECONDS = 5.0
PUBLISHER_QUEUE_DEPTH = 10
POSITION_STEP_METERS = 0.25
NANOSECONDS_PER_SECOND = 1_000_000_000

# Nominal values for deterministic simulation, not a specific battery model.
BATTERY_DRAIN_PER_SAMPLE = 0.01
BATTERY_FULL_VOLTAGE = 12.6
BATTERY_EMPTY_VOLTAGE = 9.6
BATTERY_CAPACITY_AH = 5.0
BATTERY_TEMPERATURE_CELSIUS = 25.0


def _validate_publish_rate(value: object) -> float:
    """Return a positive finite publishing rate in hertz."""
    error_message = "publish_rate_hz must be a positive finite number"
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(error_message)
    if not math.isfinite(value) or value <= 0:
        raise ValueError(error_message)
    return float(value)


class RobotSimulator(Node):
    """Publish deterministic position and battery telemetry."""

    def __init__(self) -> None:
        """Create telemetry publishers and their configurable timers."""
        super().__init__("robot_simulator")

        publish_rate = _validate_publish_rate(
            self.declare_parameter(
                "publish_rate_hz",
                DEFAULT_PUBLISH_RATE_HZ,
            ).value
        )
        self._position_pause = self._declare_pause_window(
            "position",
            DEFAULT_POSITION_PAUSE_START_SECONDS,
            DEFAULT_POSITION_PAUSE_DURATION_SECONDS,
        )
        self._battery_pause = self._declare_pause_window(
            "battery",
            DEFAULT_BATTERY_PAUSE_START_SECONDS,
            DEFAULT_BATTERY_PAUSE_DURATION_SECONDS,
        )

        self._position_publisher: Publisher = self.create_publisher(
            PoseStamped,
            POSITION_TOPIC,
            PUBLISHER_QUEUE_DEPTH,
        )
        self._battery_publisher: Publisher = self.create_publisher(
            BatteryState,
            BATTERY_TOPIC,
            PUBLISHER_QUEUE_DEPTH,
        )

        publish_period = 1.0 / publish_rate
        self._start_time = self.get_clock().now()
        self._position_sample_index = 0
        self._battery_sample_index = 0
        # Separate timers let either signal pause without stopping the other.
        self._position_timer = self.create_timer(
            publish_period,
            self._publish_position,
        )
        self._battery_timer = self.create_timer(
            publish_period,
            self._publish_battery,
        )

    def _declare_pause_window(
        self,
        signal_name: str,
        default_start_seconds: float,
        default_duration_seconds: float,
    ) -> PauseWindow:
        """Declare one signal's pause parameters and return its window."""
        start = self.declare_parameter(
            f"{signal_name}_pause_start_seconds",
            default_start_seconds,
        ).value
        duration = self.declare_parameter(
            f"{signal_name}_pause_duration_seconds",
            default_duration_seconds,
        ).value
        return PauseWindow(start_seconds=start, duration_seconds=duration)

    def _elapsed_seconds(self) -> float:
        """Return elapsed ROS-clock time since simulator initialization."""
        elapsed = self.get_clock().now() - self._start_time
        return elapsed.nanoseconds / NANOSECONDS_PER_SECOND

    def _publish_position(self) -> None:
        """Publish the next sample on the simulator's straight-line path."""
        sample_index = self._position_sample_index
        self._position_sample_index += 1
        if self._position_pause.is_active(self._elapsed_seconds()):
            return

        message = PoseStamped()
        message.header.stamp = self.get_clock().now().to_msg()
        message.header.frame_id = POSITION_FRAME_ID
        message.pose.position.x = sample_index * POSITION_STEP_METERS
        message.pose.orientation.w = 1.0

        self._position_publisher.publish(message)

    def _publish_battery(self) -> None:
        """Publish the next sample from the simulated discharging battery."""
        sample_index = self._battery_sample_index
        self._battery_sample_index += 1
        if self._battery_pause.is_active(self._elapsed_seconds()):
            return

        percentage = max(
            0.0,
            1.0 - sample_index * BATTERY_DRAIN_PER_SAMPLE,
        )
        voltage_range = BATTERY_FULL_VOLTAGE - BATTERY_EMPTY_VOLTAGE

        message = BatteryState()
        message.header.stamp = self.get_clock().now().to_msg()
        message.header.frame_id = BATTERY_FRAME_ID
        message.percentage = percentage
        message.voltage = BATTERY_EMPTY_VOLTAGE + voltage_range * percentage
        message.capacity = BATTERY_CAPACITY_AH
        message.design_capacity = BATTERY_CAPACITY_AH
        message.charge = BATTERY_CAPACITY_AH * percentage
        # Current draw is not part of this simple battery simulation.
        message.current = math.nan
        message.temperature = BATTERY_TEMPERATURE_CELSIUS
        message.power_supply_status = (
            BatteryState.POWER_SUPPLY_STATUS_DISCHARGING
            if percentage > 0.0
            else BatteryState.POWER_SUPPLY_STATUS_NOT_CHARGING
        )
        message.power_supply_health = BatteryState.POWER_SUPPLY_HEALTH_GOOD
        message.power_supply_technology = (
            BatteryState.POWER_SUPPLY_TECHNOLOGY_LION
        )
        message.present = True
        message.location = "main_battery"

        self._battery_publisher.publish(message)


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
