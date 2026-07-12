"""Publish deterministic robot telemetry for the local ROS 2 demonstration."""

from __future__ import annotations

import math

from geometry_msgs.msg import PoseStamped

import rclpy
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from rclpy.publisher import Publisher

from sensor_msgs.msg import BatteryState


POSITION_TOPIC = "/telemetry/position"
POSITION_FRAME_ID = "map"
BATTERY_TOPIC = "/telemetry/battery"
BATTERY_FRAME_ID = "base_link"
DEFAULT_PUBLISH_RATE_HZ = 1.0
PUBLISHER_QUEUE_DEPTH = 10
POSITION_STEP_METERS = 0.25

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
        self._position_sample_index = 0
        self._battery_sample_index = 0
        self._position_timer = self.create_timer(
            publish_period,
            self._publish_position,
        )
        self._battery_timer = self.create_timer(
            publish_period,
            self._publish_battery,
        )

    def _publish_position(self) -> None:
        """Publish the next sample on the simulator's straight-line path."""
        message = PoseStamped()
        message.header.stamp = self.get_clock().now().to_msg()
        message.header.frame_id = POSITION_FRAME_ID
        message.pose.position.x = (
            self._position_sample_index * POSITION_STEP_METERS
        )
        message.pose.orientation.w = 1.0

        self._position_publisher.publish(message)
        self._position_sample_index += 1

    def _publish_battery(self) -> None:
        """Publish the next sample from the simulated discharging battery."""
        percentage = max(
            0.0,
            1.0 - self._battery_sample_index * BATTERY_DRAIN_PER_SAMPLE,
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
        self._battery_sample_index += 1


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
