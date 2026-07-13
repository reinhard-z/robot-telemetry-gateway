"""Launch the local simulator-to-gateway telemetry pipeline."""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration

from launch_ros.actions import Node


def generate_launch_description() -> LaunchDescription:
    """Start both telemetry nodes with their configured defaults."""
    publisher_reliability = LaunchConfiguration("publisher_reliability")
    gateway_reliability = LaunchConfiguration("gateway_reliability")

    return LaunchDescription(
        [
            DeclareLaunchArgument(
                "publisher_reliability",
                default_value="reliable",
                description="QoS reliability offered by the simulator",
            ),
            DeclareLaunchArgument(
                "gateway_reliability",
                default_value="reliable",
                description="QoS reliability requested by the gateway",
            ),
            Node(
                package="robot_telemetry",
                executable="robot_simulator",
                output="screen",
                parameters=[{"qos_reliability": publisher_reliability}],
            ),
            Node(
                package="robot_telemetry_gateway",
                executable="telemetry_gateway",
                output="screen",
                parameters=[{"qos_reliability": gateway_reliability}],
            ),
        ]
    )
