"""Launch the local simulator-to-gateway telemetry pipeline."""

from launch import LaunchDescription

from launch_ros.actions import Node


def generate_launch_description() -> LaunchDescription:
    """Start both telemetry nodes with their configured defaults."""
    return LaunchDescription(
        [
            Node(
                package="robot_telemetry",
                executable="robot_simulator",
                output="screen",
            ),
            Node(
                package="robot_telemetry",
                executable="telemetry_gateway",
                output="screen",
            ),
        ]
    )
