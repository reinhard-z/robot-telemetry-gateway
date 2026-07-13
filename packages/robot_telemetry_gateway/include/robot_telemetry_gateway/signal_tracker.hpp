#ifndef ROBOT_TELEMETRY_GATEWAY__SIGNAL_TRACKER_HPP_
#define ROBOT_TELEMETRY_GATEWAY__SIGNAL_TRACKER_HPP_

#include <chrono>
#include <cmath>
#include <functional>
#include <optional>
#include <stdexcept>
#include <utility>

#include "robot_telemetry_gateway/telemetry_values.hpp"

namespace robot_telemetry_gateway {

// Use fractional seconds for configuration and reported receipt age.
using Seconds = std::chrono::duration<double>;

// Wall time is retained for observability, never for freshness decisions.
using WallTime = std::chrono::system_clock::time_point;

// Monotonic time is used exclusively for elapsed-time decisions.
using MonotonicTime = std::chrono::steady_clock::time_point;

// Persistent health states for one telemetry signal.
enum class SignalState { kWaiting, kHealthy, kStale };

// State changes that a caller may log or otherwise act upon.
enum class SignalTransition { kBecameHealthy, kBecameStale, kRecovered };

// Keep a decoded value together with its three distinct timestamp roles.
template <typename Value>
struct SignalMeasurement {
  Value value;
  SourceTime source_time;
  WallTime receipt_time;
  MonotonicTime monotonic_receipt_time;
};

// Track receipt age and health transitions without depending on ROS.
// Callers must serialize access; the tracker intentionally owns no locks.
template <typename Value>
class SignalTracker {
 public:
  // A small injected clock seam keeps boundary tests deterministic.
  using Clock = std::function<MonotonicTime()>;

  // Construct a tracker with a positive finite freshness threshold.
  explicit SignalTracker(
      Seconds stale_threshold,
      Clock clock = [] { return std::chrono::steady_clock::now(); })
      : stale_threshold_(stale_threshold), clock_(std::move(clock)) {
    if (!std::isfinite(stale_threshold_.count()) ||
        stale_threshold_ <= Seconds::zero()) {
      throw std::invalid_argument(
          "stale threshold must be a positive finite duration");
    }
    if (!clock_) {
      throw std::invalid_argument("clock must be callable");
    }
  }

  [[nodiscard]] SignalState state() const noexcept { return state_; }

  [[nodiscard]] Seconds stale_threshold() const noexcept {
    return stale_threshold_;
  }

  // Return tracker-owned data that is replaced by the next measurement.
  [[nodiscard]] const std::optional<SignalMeasurement<Value>>&
  latest_measurement() const noexcept {
    return latest_measurement_;
  }

  // Return the monotonic receipt age, or nothing before the first measurement.
  [[nodiscard]] std::optional<Seconds> age() {
    if (!latest_measurement_) {
      return std::nullopt;
    }

    return std::chrono::duration_cast<Seconds>(
        read_clock() - latest_measurement_->monotonic_receipt_time);
  }

  // Record an arrival and report a transition only when health changes.
  std::optional<SignalTransition> record_measurement(Value value,
                                                     SourceTime source_time,
                                                     WallTime receipt_time) {
    const MonotonicTime monotonic_receipt_time = read_clock();
    const SignalState previous_state = state_;

    latest_measurement_ = SignalMeasurement<Value>{
        std::move(value), source_time, receipt_time, monotonic_receipt_time};
    state_ = SignalState::kHealthy;

    if (previous_state == SignalState::kWaiting) {
      return SignalTransition::kBecameHealthy;
    }
    if (previous_state == SignalState::kStale) {
      return SignalTransition::kRecovered;
    }
    return std::nullopt;
  }

  // Evaluate staleness and suppress notifications for unchanged states.
  std::optional<SignalTransition> check_health() {
    if (state_ != SignalState::kHealthy) {
      return std::nullopt;
    }

    const std::optional<Seconds> current_age = age();
    if (current_age && *current_age >= stale_threshold_) {
      state_ = SignalState::kStale;
      return SignalTransition::kBecameStale;
    }
    return std::nullopt;
  }

 private:
  // Validate the injected clock so elapsed-time decisions cannot go backwards.
  MonotonicTime read_clock() {
    const MonotonicTime current_time = clock_();
    if (last_clock_reading_ && current_time < *last_clock_reading_) {
      throw std::runtime_error("monotonic clock must not move backwards");
    }

    last_clock_reading_ = current_time;
    return current_time;
  }

  Seconds stale_threshold_;
  Clock clock_;
  SignalState state_{SignalState::kWaiting};
  std::optional<SignalMeasurement<Value>> latest_measurement_;
  std::optional<MonotonicTime> last_clock_reading_;
};

}  // namespace robot_telemetry_gateway

#endif  // ROBOT_TELEMETRY_GATEWAY__SIGNAL_TRACKER_HPP_
