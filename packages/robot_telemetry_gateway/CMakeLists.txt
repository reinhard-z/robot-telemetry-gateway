cmake_minimum_required(VERSION 3.16)

project(robot_telemetry_gateway VERSION 0.1.0 LANGUAGES CXX)

find_package(ament_cmake REQUIRED)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

ament_package()
