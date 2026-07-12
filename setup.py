from setuptools import find_packages, setup


package_name = "robot_telemetry"


setup(
    name=package_name,
    version="0.1.0",
    packages=find_packages(exclude=("test",)),
    data_files=[
        (
            "share/ament_index/resource_index/packages",
            [f"resource/{package_name}"],
        ),
        (f"share/{package_name}", ["package.xml"]),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="Reinhard Zach",
    maintainer_email="31817478+reinhard-z@users.noreply.github.com",
    description="ROS 2 telemetry simulator and freshness-tracking gateway.",
    license="MIT",
    url="https://github.com/reinhard-z/robot-telemetry-gateway",
    tests_require=["pytest"],
    entry_points={
        "console_scripts": [
            "robot_simulator = robot_telemetry.simulator_node:main",
            "telemetry_gateway = robot_telemetry.gateway_node:main",
        ],
    },
)
