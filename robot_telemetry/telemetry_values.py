"""Pure Python values decoded from ROS telemetry messages."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PositionValue:
    """Represent the Cartesian position used by the gateway."""

    x: float
    y: float
    z: float


@dataclass(frozen=True)
class BatteryValue:
    """Represent the battery measurements retained by the gateway."""

    percentage: float
    voltage: float
    charge: float
