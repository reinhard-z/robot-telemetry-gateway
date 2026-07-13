import unittest
from pathlib import Path
from xml.etree import ElementTree

import robot_telemetry


class PackageMetadataTest(unittest.TestCase):
    """Keep the ROS package metadata aligned with the Python package."""

    def setUp(self) -> None:
        package_xml = Path(__file__).parents[1] / "package.xml"
        self.metadata = ElementTree.parse(package_xml).getroot()

    def test_package_name_matches_python_module(self) -> None:
        """The ament package name must remain importable by the same name."""
        self.assertEqual(self.metadata.findtext("name"), robot_telemetry.__name__)

    def test_package_declares_a_version_and_license(self) -> None:
        """Required release metadata must remain explicit."""
        self.assertEqual(self.metadata.findtext("version"), "0.2.0")
        self.assertEqual(self.metadata.findtext("license"), "MIT")

    def test_cpp_gateway_is_a_runtime_dependency(self) -> None:
        """The installed launch file must bring in its C++ gateway package."""
        dependencies = {
            element.text for element in self.metadata.findall("exec_depend")
        }
        self.assertIn("robot_telemetry_gateway", dependencies)


if __name__ == "__main__":
    unittest.main()
