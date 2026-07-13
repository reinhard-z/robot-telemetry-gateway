#include "message_conversion.hpp"

namespace robot_telemetry_gateway {

SourceTime decode_source_time(const builtin_interfaces::msg::Time& timestamp) {
  return SourceTime{timestamp.sec, timestamp.nanosec};
}

PositionValue decode_position(const geometry_msgs::msg::PoseStamped& message) {
  const auto& position = message.pose.position;
  return PositionValue{position.x, position.y, position.z};
}

BatteryValue decode_battery(const sensor_msgs::msg::BatteryState& message) {
  return BatteryValue{message.percentage, message.voltage, message.charge};
}

}  // namespace robot_telemetry_gateway
