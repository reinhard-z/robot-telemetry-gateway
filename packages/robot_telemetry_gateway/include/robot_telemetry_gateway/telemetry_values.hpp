#ifndef ROBOT_TELEMETRY_GATEWAY__TELEMETRY_VALUES_HPP_
#define ROBOT_TELEMETRY_GATEWAY__TELEMETRY_VALUES_HPP_

#include <cstdint>

namespace robot_telemetry_gateway {

// Preserve the source timestamp exactly without using it for elapsed time.
struct SourceTime {
  std::int32_t seconds{0};
  std::uint32_t nanoseconds{0};

  bool operator==(const SourceTime&) const = default;
};

// Store the Cartesian position used by the gateway health model.
struct PositionValue {
  double x{0.0};
  double y{0.0};
  double z{0.0};

  bool operator==(const PositionValue&) const = default;
};

// Store the battery measurements retained by the gateway.
struct BatteryValue {
  double percentage{0.0};
  double voltage{0.0};
  double charge{0.0};

  bool operator==(const BatteryValue&) const = default;
};

}  // namespace robot_telemetry_gateway

#endif  // ROBOT_TELEMETRY_GATEWAY__TELEMETRY_VALUES_HPP_
