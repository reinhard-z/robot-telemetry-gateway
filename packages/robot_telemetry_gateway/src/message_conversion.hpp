#ifndef ROBOT_TELEMETRY_GATEWAY_MESSAGE_CONVERSION_HPP_
#define ROBOT_TELEMETRY_GATEWAY_MESSAGE_CONVERSION_HPP_

#include <builtin_interfaces/msg/time.hpp>
#include <geometry_msgs/msg/pose_stamped.hpp>
#include <sensor_msgs/msg/battery_state.hpp>

#include "robot_telemetry_gateway/telemetry_values.hpp"

namespace robot_telemetry_gateway {

// Preserve the ROS source timestamp without using it for freshness arithmetic.
[[nodiscard]] SourceTime decode_source_time(
    const builtin_interfaces::msg::Time& timestamp);

// Decode the position fields retained by the gateway health model.
[[nodiscard]] PositionValue decode_position(
    const geometry_msgs::msg::PoseStamped& message);

// Decode the battery fields retained by the gateway health model.
[[nodiscard]] BatteryValue decode_battery(
    const sensor_msgs::msg::BatteryState& message);

}  // namespace robot_telemetry_gateway

#endif  // ROBOT_TELEMETRY_GATEWAY_MESSAGE_CONVERSION_HPP_
