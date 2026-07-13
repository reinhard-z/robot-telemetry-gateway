#include "robot_telemetry_gateway/signal_tracker.hpp"

#include <gtest/gtest.h>

#include <chrono>
#include <limits>
#include <optional>
#include <stdexcept>

namespace robot_telemetry_gateway {
namespace {

using namespace std::chrono_literals;

// Provide a controllable steady clock without sleeping in tests.
class FakeClock {
 public:
  explicit FakeClock(MonotonicTime initial_time)
      : current_time_(initial_time) {}

  [[nodiscard]] MonotonicTime now() const noexcept { return current_time_; }

  void advance(Seconds elapsed) {
    current_time_ +=
        std::chrono::duration_cast<std::chrono::steady_clock::duration>(
            elapsed);
  }

 private:
  MonotonicTime current_time_;
};

// Exercise the tracker with deterministic source, wall, and monotonic times.
class SignalTrackerTest : public ::testing::Test {
 protected:
  using Tracker = SignalTracker<PositionValue>;

  SignalTrackerTest()
      : clock_(MonotonicTime{100s}),
        tracker_(Seconds{2.5}, [this] { return clock_.now(); }) {}

  std::optional<SignalTransition> record_position(
      PositionValue value = PositionValue{1.0, 2.0, 3.0}) {
    return tracker_.record_measurement(value, source_time_, receipt_time_);
  }

  FakeClock clock_;
  Tracker tracker_;
  const SourceTime source_time_{1'720'000'000, 123'456'789};
  const WallTime receipt_time_{std::chrono::seconds{1'720'000'001}};
};

TEST_F(SignalTrackerTest, WaitsBeforeTheFirstMeasurement) {
  EXPECT_EQ(tracker_.state(), SignalState::kWaiting);
  EXPECT_FALSE(tracker_.latest_measurement());
  EXPECT_FALSE(tracker_.age());
  EXPECT_FALSE(tracker_.check_health());
}

TEST_F(SignalTrackerTest, FirstMeasurementBecomesHealthyAndRetainsData) {
  const PositionValue value{12.5, -3.0, 0.25};

  const auto transition = record_position(value);

  ASSERT_TRUE(transition);
  EXPECT_EQ(*transition, SignalTransition::kBecameHealthy);
  EXPECT_EQ(tracker_.state(), SignalState::kHealthy);

  const auto& measurement = tracker_.latest_measurement();
  ASSERT_TRUE(measurement);
  EXPECT_EQ(measurement->value, value);
  EXPECT_EQ(measurement->source_time, source_time_);
  EXPECT_EQ(measurement->receipt_time, receipt_time_);
  EXPECT_EQ(measurement->monotonic_receipt_time, clock_.now());

  const auto current_age = tracker_.age();
  ASSERT_TRUE(current_age);
  EXPECT_DOUBLE_EQ(current_age->count(), 0.0);
}

TEST_F(SignalTrackerTest, HealthyMeasurementResetsAgeWithoutATransition) {
  record_position();
  clock_.advance(Seconds{2.0});
  const PositionValue next_value{4.0, 5.0, 6.0};
  const SourceTime next_source_time{source_time_.seconds + 2,
                                    source_time_.nanoseconds};
  const WallTime next_receipt_time = receipt_time_ + 2s;

  const auto transition = tracker_.record_measurement(
      next_value, next_source_time, next_receipt_time);

  EXPECT_FALSE(transition);
  EXPECT_EQ(tracker_.state(), SignalState::kHealthy);
  const auto& measurement = tracker_.latest_measurement();
  ASSERT_TRUE(measurement);
  EXPECT_EQ(measurement->value, next_value);
  EXPECT_EQ(measurement->source_time, next_source_time);
  EXPECT_EQ(measurement->receipt_time, next_receipt_time);

  const auto current_age = tracker_.age();
  ASSERT_TRUE(current_age);
  EXPECT_DOUBLE_EQ(current_age->count(), 0.0);
}

TEST_F(SignalTrackerTest, AgeBelowTheThresholdRemainsHealthy) {
  record_position();
  clock_.advance(Seconds{2.49});

  const auto current_age = tracker_.age();
  ASSERT_TRUE(current_age);
  EXPECT_DOUBLE_EQ(current_age->count(), 2.49);
  EXPECT_FALSE(tracker_.check_health());
  EXPECT_EQ(tracker_.state(), SignalState::kHealthy);
}

TEST_F(SignalTrackerTest, AgeExactlyAtTheThresholdBecomesStale) {
  record_position();
  clock_.advance(Seconds{2.5});

  const auto transition = tracker_.check_health();

  ASSERT_TRUE(transition);
  EXPECT_EQ(*transition, SignalTransition::kBecameStale);
  EXPECT_EQ(tracker_.state(), SignalState::kStale);
}

TEST_F(SignalTrackerTest, StaleTransitionIsNotRepeated) {
  record_position();
  clock_.advance(Seconds{3.0});

  const auto transition = tracker_.check_health();

  ASSERT_TRUE(transition);
  EXPECT_EQ(*transition, SignalTransition::kBecameStale);
  EXPECT_FALSE(tracker_.check_health());
  EXPECT_EQ(tracker_.state(), SignalState::kStale);
}

TEST_F(SignalTrackerTest, NextMeasurementRecoversAStaleSignal) {
  record_position();
  clock_.advance(Seconds{2.5});
  tracker_.check_health();

  const auto transition = record_position();

  ASSERT_TRUE(transition);
  EXPECT_EQ(*transition, SignalTransition::kRecovered);
  EXPECT_EQ(tracker_.state(), SignalState::kHealthy);
}

TEST_F(SignalTrackerTest, TrackerTemplateRetainsBatteryMeasurements) {
  SignalTracker<BatteryValue> battery_tracker(Seconds{2.5},
                                              [this] { return clock_.now(); });
  const BatteryValue battery{0.75, 24.0, 8.5};

  battery_tracker.record_measurement(battery, source_time_, receipt_time_);

  const auto& measurement = battery_tracker.latest_measurement();
  ASSERT_TRUE(measurement);
  EXPECT_EQ(measurement->value, battery);
  EXPECT_EQ(measurement->source_time, source_time_);
  EXPECT_EQ(measurement->receipt_time, receipt_time_);
}

TEST(SignalTrackerConstructionTest, RejectsInvalidThresholds) {
  const double invalid_thresholds[] = {
      0.0,
      -1.0,
      std::numeric_limits<double>::infinity(),
      -std::numeric_limits<double>::infinity(),
      std::numeric_limits<double>::quiet_NaN(),
  };

  for (const double threshold : invalid_thresholds) {
    EXPECT_THROW(SignalTracker<PositionValue>(Seconds{threshold}),
                 std::invalid_argument);
  }
}

TEST(SignalTrackerConstructionTest, RejectsAnEmptyClock) {
  EXPECT_THROW(SignalTracker<PositionValue>(
                   Seconds{2.5}, SignalTracker<PositionValue>::Clock{}),
               std::invalid_argument);
}

TEST_F(SignalTrackerTest, RejectsAClockThatMovesBackwards) {
  record_position();
  clock_.advance(Seconds{-1.0});

  EXPECT_THROW(static_cast<void>(tracker_.age()), std::runtime_error);
}

}  // namespace
}  // namespace robot_telemetry_gateway
