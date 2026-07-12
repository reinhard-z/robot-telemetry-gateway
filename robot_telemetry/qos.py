"""Build the shared ROS 2 QoS profile for telemetry topics."""

from __future__ import annotations

from rclpy.qos import HistoryPolicy, QoSProfile, ReliabilityPolicy


DEFAULT_QOS_RELIABILITY = "reliable"
TELEMETRY_QUEUE_DEPTH = 10

_RELIABILITY_POLICIES = {
    "reliable": ReliabilityPolicy.RELIABLE,
    "best_effort": ReliabilityPolicy.BEST_EFFORT,
}


def telemetry_qos_profile(reliability: object) -> QoSProfile:
    """Return the fixed telemetry profile with the selected reliability."""
    if (
        not isinstance(reliability, str)
        or reliability not in _RELIABILITY_POLICIES
    ):
        raise ValueError(
            "qos_reliability must be 'reliable' or 'best_effort'"
        )

    return QoSProfile(
        history=HistoryPolicy.KEEP_LAST,
        depth=TELEMETRY_QUEUE_DEPTH,
        reliability=_RELIABILITY_POLICIES[reliability],
    )
