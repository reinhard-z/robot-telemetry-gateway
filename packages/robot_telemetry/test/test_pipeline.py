"""Run the telemetry pipeline contract against the C++ gateway."""

from __future__ import annotations

import os
import unittest

try:
    from launch import LaunchDescription

    import launch_testing
    import launch_testing.markers

    import pytest

    from pipeline_contract import (
        PipelineContractMixin,
        PipelineShutdownMixin,
        build_pipeline_test_description,
    )
except ImportError as error:
    if "ROS_DISTRO" in os.environ:
        raise
    raise unittest.SkipTest("requires a sourced ROS 2 environment") from error


@pytest.mark.launch_test
@launch_testing.markers.keep_alive
def generate_test_description() -> tuple[LaunchDescription, dict[str, object]]:
    """Launch the production gateway for every QoS pairing."""
    return build_pipeline_test_description()


class PipelineTest(PipelineContractMixin, unittest.TestCase):
    """Apply the shared contract to the production gateway."""


@launch_testing.post_shutdown_test()
class PipelineShutdownTest(PipelineShutdownMixin, unittest.TestCase):
    """Apply the shared shutdown contract to the production pipeline."""
