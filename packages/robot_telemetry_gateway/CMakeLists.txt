cmake_minimum_required(VERSION 3.16)

project(robot_telemetry_gateway VERSION 0.1.0 LANGUAGES CXX)

find_package(ament_cmake REQUIRED)

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

install(
  TARGETS ${PROJECT_NAME}_health
  EXPORT export_${PROJECT_NAME}
)
install(DIRECTORY include/ DESTINATION include)

if(BUILD_TESTING)
  find_package(ament_cmake_gtest REQUIRED)

  ament_add_gtest(signal_tracker_test test/signal_tracker_test.cpp)
  target_link_libraries(signal_tracker_test ${PROJECT_NAME}_health)
endif()

ament_export_targets(export_${PROJECT_NAME})
ament_export_include_directories(include)

ament_package()
