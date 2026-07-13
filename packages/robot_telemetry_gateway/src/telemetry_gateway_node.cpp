#include <chrono>
#include <cmath>
#include <cstddef>
#include <cstdlib>
#include <ctime>
#include <geometry_msgs/msg/pose_stamped.hpp>
#include <iomanip>
#include <iostream>
#include <memory>
#include <optional>
#include <rclcpp/rclcpp.hpp>
#include <sensor_msgs/msg/battery_state.hpp>
#include <sstream>
#include <stdexcept>
#include <string>

#include "message_conversion.hpp"
#include "robot_telemetry_gateway/signal_tracker.hpp"

namespace robot_telemetry_gateway {
namespace {

using namespace std::chrono_literals;

constexpr char kNodeName[] = "telemetry_gateway";
constexpr char kPositionTopic[] = "/telemetry/position";
constexpr char kBatteryTopic[] = "/telemetry/battery";
constexpr char kPositionThresholdParameter[] =
    "position_stale_threshold_seconds";
constexpr char kBatteryThresholdParameter[] = "battery_stale_threshold_seconds";
constexpr char kQosReliabilityParameter[] = "qos_reliability";
constexpr double kDefaultStaleThresholdSeconds = 2.5;
constexpr std::size_t kTelemetryQueueDepth = 10;
constexpr auto kHealthCheckPeriod = 250ms;

// Declare one threshold and fail early with the parameter name in the error.
Seconds declare_stale_threshold(rclcpp::Node& node,
                                const std::string& parameter_name) {
  const double threshold = node.declare_parameter<double>(
      parameter_name, kDefaultStaleThresholdSeconds);
  if (!std::isfinite(threshold) || threshold <= 0.0) {
    throw std::invalid_argument(parameter_name +
                                " must be a positive finite number");
  }
  return Seconds{threshold};
}

// Keep all QoS settings fixed except for the configured reliability policy.
rclcpp::QoS declare_telemetry_qos(rclcpp::Node& node) {
  const std::string reliability =
      node.declare_parameter<std::string>(kQosReliabilityParameter, "reliable");
  rclcpp::QoS qos{rclcpp::KeepLast{kTelemetryQueueDepth}};
  qos.durability_volatile();

  if (reliability == "reliable") {
    qos.reliable();
    return qos;
  }
  if (reliability == "best_effort") {
    qos.best_effort();
    return qos;
  }

  throw std::invalid_argument(
      "qos_reliability must be 'reliable' or 'best_effort'");
}

// Format system time as UTC while retaining nanosecond precision in the log.
std::string format_wall_time(WallTime timestamp) {
  const auto whole_seconds =
      std::chrono::floor<std::chrono::seconds>(timestamp);
  const auto nanoseconds = std::chrono::duration_cast<std::chrono::nanoseconds>(
      timestamp - whole_seconds);
  const std::time_t raw_time =
      std::chrono::system_clock::to_time_t(whole_seconds);
  std::tm utc_time{};
  if (::gmtime_r(&raw_time, &utc_time) == nullptr) {
    throw std::runtime_error("failed to format a telemetry timestamp");
  }

  std::ostringstream output;
  output << std::put_time(&utc_time, "%Y-%m-%dT%H:%M:%S") << '.'
         << std::setfill('0') << std::setw(9) << nanoseconds.count()
         << "+00:00";
  return output.str();
}

// Convert source metadata only for logging; freshness never uses this value.
std::string format_source_time(SourceTime timestamp) {
  const auto duration = std::chrono::duration_cast<WallTime::duration>(
      std::chrono::seconds{timestamp.seconds} +
      std::chrono::nanoseconds{timestamp.nanoseconds});
  return format_wall_time(WallTime{duration});
}

// Log one transition and ignore unchanged state returned as no value.
template <typename Value>
void log_transition(const rclcpp::Logger& logger, const char* signal_name,
                    SignalTracker<Value>& tracker,
                    std::optional<SignalTransition> transition) {
  if (!transition) {
    return;
  }

  switch (*transition) {
    case SignalTransition::kBecameHealthy:
      RCLCPP_INFO(logger, "%s: waiting -> healthy", signal_name);
      return;

    case SignalTransition::kBecameStale: {
      const std::optional<Seconds> age = tracker.age();
      if (!age) {
        throw std::logic_error("a stale signal must have a receipt time");
      }
      RCLCPP_WARN(logger, "%s: healthy -> stale (age=%.2fs, threshold=%.2fs)",
                  signal_name, age->count(), tracker.stale_threshold().count());
      return;
    }

    case SignalTransition::kRecovered: {
      const auto& measurement = tracker.latest_measurement();
      if (!measurement) {
        throw std::logic_error(
            "a recovered signal must have recorded timestamps");
      }
      const std::string source_time =
          format_source_time(measurement->source_time);
      const std::string receipt_time =
          format_wall_time(measurement->receipt_time);
      RCLCPP_INFO(logger,
                  "%s: stale -> recovered (measurement_time=%s, "
                  "receipt_time=%s)",
                  signal_name, source_time.c_str(), receipt_time.c_str());
      return;
    }
  }

  throw std::logic_error("unsupported signal transition");
}

}  // namespace

// Receive both telemetry streams and evaluate their health on one wall timer.
// rclcpp::spin uses a single-threaded executor, so callbacks serialize access.
class TelemetryGateway final : public rclcpp::Node {
 public:
  TelemetryGateway()
      : Node(kNodeName),
        position_tracker_(
            declare_stale_threshold(*this, kPositionThresholdParameter)),
        battery_tracker_(
            declare_stale_threshold(*this, kBatteryThresholdParameter)) {
    const rclcpp::QoS qos = declare_telemetry_qos(*this);

    position_subscription_ =
        create_subscription<geometry_msgs::msg::PoseStamped>(
            kPositionTopic, qos,
            [this](geometry_msgs::msg::PoseStamped::ConstSharedPtr message) {
              record_position(*message);
            });
    battery_subscription_ = create_subscription<sensor_msgs::msg::BatteryState>(
        kBatteryTopic, qos,
        [this](sensor_msgs::msg::BatteryState::ConstSharedPtr message) {
          record_battery(*message);
        });
    health_timer_ = create_wall_timer(kHealthCheckPeriod,
                                      [this] { check_signal_health(); });
  }

 private:
  // Decode and record one position measurement at the ROS boundary.
  void record_position(const geometry_msgs::msg::PoseStamped& message) {
    const WallTime receipt_time = std::chrono::system_clock::now();
    const auto transition = position_tracker_.record_measurement(
        decode_position(message), decode_source_time(message.header.stamp),
        receipt_time);
    log_transition(get_logger(), "position", position_tracker_, transition);
  }

  // Decode and record one battery measurement at the ROS boundary.
  void record_battery(const sensor_msgs::msg::BatteryState& message) {
    const WallTime receipt_time = std::chrono::system_clock::now();
    const auto transition = battery_tracker_.record_measurement(
        decode_battery(message), decode_source_time(message.header.stamp),
        receipt_time);
    log_transition(get_logger(), "battery", battery_tracker_, transition);
  }

  // Evaluate both trackers independently on each timer tick.
  void check_signal_health() {
    log_transition(get_logger(), "position", position_tracker_,
                   position_tracker_.check_health());
    log_transition(get_logger(), "battery", battery_tracker_,
                   battery_tracker_.check_health());
  }

  SignalTracker<PositionValue> position_tracker_;
  SignalTracker<BatteryValue> battery_tracker_;
  rclcpp::Subscription<geometry_msgs::msg::PoseStamped>::SharedPtr
      position_subscription_;
  rclcpp::Subscription<sensor_msgs::msg::BatteryState>::SharedPtr
      battery_subscription_;
  rclcpp::TimerBase::SharedPtr health_timer_;
};

}  // namespace robot_telemetry_gateway

// Run until ROS shuts down and return a non-zero code for startup/runtime
// errors.
int main(int argc, char* argv[]) {
  try {
    rclcpp::init(argc, argv);
    rclcpp::spin(std::make_shared<robot_telemetry_gateway::TelemetryGateway>());
    if (rclcpp::ok()) {
      rclcpp::shutdown();
    }
    return EXIT_SUCCESS;
  } catch (const std::exception& error) {
    std::cerr << "telemetry_gateway: " << error.what() << '\n';
    if (rclcpp::ok()) {
      rclcpp::shutdown();
    }
    return EXIT_FAILURE;
  }
}
