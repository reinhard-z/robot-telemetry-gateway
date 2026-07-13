#include "message_conversion.hpp"

#include <gtest/gtest.h>

#include <builtin_interfaces/msg/time.hpp>
#include <geometry_msgs/msg/pose_stamped.hpp>
#include <sensor_msgs/msg/battery_state.hpp>

#include "robot_telemetry_gateway/telemetry_values.hpp"

namespace robot_telemetry_gateway {
namespace {

TEST(MessageConversionTest, PreservesSourceTimeExactly) {
  builtin_interfaces::msg::Time timestamp;
  timestamp.sec = -123;
  timestamp.nanosec = 999'999'999;
  const SourceTime expected{-123, 999'999'999};

  EXPECT_EQ(decode_source_time(timestamp), expected);
}

TEST(MessageConversionTest, DecodesPositionFields) {
  geometry_msgs::msg::PoseStamped message;
  message.pose.position.x = 1.25;
  message.pose.position.y = -2.5;
  message.pose.position.z = 3.75;
  const PositionValue expected{1.25, -2.5, 3.75};

  EXPECT_EQ(decode_position(message), expected);
}

TEST(MessageConversionTest, DecodesBatteryFields) {
  sensor_msgs::msg::BatteryState message;
  message.percentage = 0.75F;
  message.voltage = 24.5F;
  message.charge = 8.25F;
  const BatteryValue expected{0.75, 24.5, 8.25};

  EXPECT_EQ(decode_battery(message), expected);
}

}  // namespace
}  // namespace robot_telemetry_gateway
