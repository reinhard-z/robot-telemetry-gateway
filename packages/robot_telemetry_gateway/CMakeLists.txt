cmake_minimum_required(VERSION 3.16)

project(robot_telemetry_gateway VERSION 0.2.0 LANGUAGES CXX)

find_package(ament_cmake REQUIRED)
find_package(builtin_interfaces REQUIRED)
find_package(geometry_msgs REQUIRED)
find_package(rclcpp REQUIRED)
find_package(sensor_msgs REQUIRED)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

# Share headers, language features, and warnings across project-owned targets.
add_library(${PROJECT_NAME}_health INTERFACE)
target_compile_features(${PROJECT_NAME}_health INTERFACE cxx_std_20)
target_include_directories(
  ${PROJECT_NAME}_health
  INTERFACE
    $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
    $<INSTALL_INTERFACE:include>
)

if(CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang")
  target_compile_options(
    ${PROJECT_NAME}_health INTERFACE -Wall -Wextra -Wpedantic
  )
endif()

add_library(
  ${PROJECT_NAME}_message_conversion STATIC
  src/message_conversion.cpp
)
target_include_directories(
  ${PROJECT_NAME}_message_conversion
  PUBLIC $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/src>
)
target_link_libraries(
  ${PROJECT_NAME}_message_conversion
  PUBLIC
    ${PROJECT_NAME}_health
    builtin_interfaces::builtin_interfaces
    geometry_msgs::geometry_msgs
    sensor_msgs::sensor_msgs
)

add_executable(telemetry_gateway src/telemetry_gateway_node.cpp)
target_link_libraries(
  telemetry_gateway
  PRIVATE
    ${PROJECT_NAME}_health
    ${PROJECT_NAME}_message_conversion
    geometry_msgs::geometry_msgs
    rclcpp::rclcpp
    sensor_msgs::sensor_msgs
)

install(
  TARGETS ${PROJECT_NAME}_health
  EXPORT export_${PROJECT_NAME}
)
install(DIRECTORY include/ DESTINATION include)
install(TARGETS telemetry_gateway DESTINATION lib/${PROJECT_NAME})

if(BUILD_TESTING)
  find_package(ament_cmake_gtest REQUIRED)

  ament_add_gtest(signal_tracker_test test/signal_tracker_test.cpp)
  target_link_libraries(signal_tracker_test ${PROJECT_NAME}_health)

  ament_add_gtest(
    message_conversion_test
    test/message_conversion_test.cpp
  )
  target_link_libraries(
    message_conversion_test ${PROJECT_NAME}_message_conversion
  )
endif()

ament_export_targets(export_${PROJECT_NAME})
ament_export_include_directories(include)

ament_package()
