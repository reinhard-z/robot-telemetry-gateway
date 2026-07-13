# Robot Telemetry Gateway

A deliberately small Python, C++, and ROS 2 project demonstrating telemetry
freshness, stale-signal recovery, and QoS trade-offs at the robot-to-platform
boundary.

![Terminal demo showing independent stale and recovery transitions](docs/assets/telemetry-demo.gif)

The battery and position streams become stale and recover independently before
both ROS nodes shut down cleanly.

## Why this project exists

I have spent more than a decade building and leading production software across
frontend, backend, data, delivery, and observability. This project is a bounded
step toward robot-near platform software: it gives me practical C++ and ROS 2
experience without pretending that a small repository makes me a robotics or
C++ specialist.

The focus is one understandable, tested telemetry path. Python keeps failure
simulation quick to change, while C++ handles the long-running gateway node.
The migration was delivered in small issues and pull requests, with behavioral
parity proven before the default pipeline changed.

## Architecture

```text
robot_telemetry (Python / rclpy)
ROS 2 simulator
  ├── position telemetry (1 Hz)
  └── battery telemetry  (1 Hz)
              │  ROS 2 topics
              ▼
robot_telemetry_gateway (C++20 / rclcpp)
C++ gateway
  ├── records measurement and receipt times
  ├── tracks signal freshness independently
  └── logs healthy, stale, and recovered transitions
```

| Package | Language | Responsibility |
| --- | --- | --- |
| [`robot_telemetry`](packages/robot_telemetry) | Python | Deterministic simulator, launch file, QoS helper, and cross-language integration tests |
| [`robot_telemetry_gateway`](packages/robot_telemetry_gateway) | C++20 | ROS subscriptions, message conversion, freshness model, transition logging, and GoogleTest unit tests |

| Signal | Topic | ROS 2 message | Default rate | Stale threshold | Default pause |
| --- | --- | --- | ---: | ---: | --- |
| Position | `/telemetry/position` | `geometry_msgs/msg/PoseStamped` | 1 Hz | 2.5 s | `[21 s, 26 s)` |
| Battery | `/telemetry/battery` | `sensor_msgs/msg/BatteryState` | 1 Hz | 2.5 s | `[8 s, 13 s)` |

The simulator pauses individual signals on a deterministic schedule. The
gateway detects each pause and recovery independently, without requiring
external hardware. Pause windows include their start and exclude their end; a
zero-second duration disables a pause. Simulated values continue advancing
while publishing is paused. Position advances by 0.25 metres per sample, while
battery percentage, charge, and voltage decrease deterministically. Battery
current remains `NaN` because current draw is deliberately not modeled.

The 2.5-second freshness threshold tolerates one delayed or missed update from
a 1 Hz signal without immediately declaring it stale.

### Language boundary

ROS-specific publishing stays in the Python
[`simulator_node.py`](packages/robot_telemetry/robot_telemetry/simulator_node.py).
Subscription and message conversion live in the C++
[`telemetry_gateway_node.cpp`](packages/robot_telemetry_gateway/src/telemetry_gateway_node.cpp).
The gateway decodes ROS messages into small
[value types](packages/robot_telemetry_gateway/include/robot_telemetry_gateway/telemetry_values.hpp)
before passing them to the ROS-independent
[`SignalTracker`](packages/robot_telemetry_gateway/include/robot_telemetry_gateway/signal_tracker.hpp).
[`PauseWindow`](packages/robot_telemetry/robot_telemetry/pause_window.py) is
isolated in pure Python. Both domain behaviors can therefore be tested without
starting a ROS graph.

The simulator remains Python because it is test tooling built for fast,
deterministic scenario changes. Porting it would add another C++ node without
creating a more useful runtime boundary. The gateway is C++ because it is the
long-running, robot-facing component and provides a focused place to learn
`rclcpp`, CMake, RAII, templates, `std::chrono`, and GoogleTest.

### Ownership, execution, and time

`SignalTracker` owns its latest decoded measurement by value in
`std::optional`. The ROS node uses the `SharedPtr` types expected by `rclcpp`
for subscriptions and its timer, and the node itself is created with
`std::make_shared` for `rclcpp::spin`. Scope and RAII handle cleanup; there are
no owning raw pointers or manual `delete` calls.

The node intentionally uses the single-threaded executor behind `rclcpp::spin`.
Position, battery, and timer callbacks therefore access the trackers serially,
so the model does not need locks. Moving to a multi-threaded executor or
reentrant callback groups would require explicit synchronization or isolated
callback groups.

Each received signal retains three notions of time:

| Time | Source | Purpose |
| --- | --- | --- |
| Measurement time | ROS message header | Explain when the simulator produced the sample |
| Wall-clock receipt time | `std::chrono::system_clock` | Produce readable recovery logs |
| Monotonic receipt time | `std::chrono::steady_clock` | Calculate age and make freshness decisions |

Freshness never depends on the robot's clock or the system wall clock. Using
monotonic receipt age prevents clock corrections or a misconfigured source
clock from producing invalid stale-state decisions.

## Run locally

The development environment uses ROS 2 Lyrical on Ubuntu 26.04 in Docker. It has
been tested with Docker Desktop on Apple Silicon.

Build the development image from the repository root:

```bash
docker build --tag robot-telemetry-gateway:lyrical .
```

Start a shell with the repository mounted below the ROS workspace source
directory:

```bash
./scripts/ros.sh
```

Check the project-owned C++ formatting inside the container:

```bash
find src/robot_telemetry_gateway/packages/robot_telemetry_gateway -type f \
  \( -name '*.cpp' -o -name '*.hpp' \) -print0 \
  | xargs -0 clang-format --dry-run --Werror
```

Build, source, and test both packages:

```bash
colcon build --symlink-install
source install/setup.bash
colcon test --event-handlers console_direct+
colcon test-result --verbose
```

The pure Python tests can also run directly on the host. ROS-only tests are
skipped there and run authoritatively in the Lyrical container:

```bash
PYTHONPATH=packages/robot_telemetry \
  python3 -m unittest discover -s packages/robot_telemetry/test -v
```

After building and sourcing the workspace, launch the complete local pipeline:

```bash
ros2 launch robot_telemetry local_pipeline.launch.py
```

The simulator and gateway run together until you stop them with `Ctrl+C`.
Both use reliable QoS by default. Select either `reliable` or `best_effort`
independently for the publisher and gateway:

```bash
ros2 launch robot_telemetry local_pipeline.launch.py \
  publisher_reliability:=best_effort \
  gateway_reliability:=best_effort
```

The container is removed when its shell exits, so its build artifacts last only
for that development session.

### Runtime parameters

The launch file exposes independent `publisher_reliability` and
`gateway_reliability` arguments. The nodes also validate these ROS parameters
when they start:

| Simulator parameter | Default | Purpose |
| --- | ---: | --- |
| `publish_rate_hz` | `1.0` | Publishing rate for both signals |
| `battery_pause_start_seconds` | `8.0` | Start of the battery pause |
| `battery_pause_duration_seconds` | `5.0` | Battery pause length; `0.0` disables it |
| `position_pause_start_seconds` | `21.0` | Start of the position pause |
| `position_pause_duration_seconds` | `5.0` | Position pause length; `0.0` disables it |
| `qos_reliability` | `reliable` | Reliability offered for both topics |

| Gateway parameter | Default | Purpose |
| --- | ---: | --- |
| `position_stale_threshold_seconds` | `2.5` | Maximum accepted position receipt age |
| `battery_stale_threshold_seconds` | `2.5` | Maximum accepted battery receipt age |
| `qos_reliability` | `reliable` | Reliability requested for both topics |

Parameters other than the launch-level QoS arguments can be exercised by
running either node directly with standard ROS arguments:

```bash
ros2 run robot_telemetry robot_simulator --ros-args \
  -p publish_rate_hz:=2.0 \
  -p battery_pause_duration_seconds:=0.0

ros2 run robot_telemetry_gateway telemetry_gateway --ros-args \
  -p position_stale_threshold_seconds:=1.5 \
  -p battery_stale_threshold_seconds:=1.5
```

## Test strategy

| Layer | What it proves |
| --- | --- |
| C++ GoogleTests | Tracker states, threshold boundaries, timestamps, retained values, validation, fake-clock behavior, and ROS message conversion |
| Python unit tests | Pause-window boundaries, invalid input, package metadata, and QoS configuration |
| ROS launch tests | Changing data, all six health transitions, all four reliability pairings, invalid startup, and clean process shutdown |

The launch contract originally ran against both gateway implementations. Only
after the C++ gateway produced the same observable behavior did the default
launch switch and the duplicate Python gateway get removed. The tagged
`v0.1.0` baseline and Git history retain that migration trail.

## QoS compatibility experiment

The experiment was repeated with the C++ subscriber after the migration. It
kept telemetry history, queue depth, and durability fixed while varying only
publisher and subscriber reliability. For each pairing, the position and
battery endpoints were inspected while the pipeline was running:

```bash
ros2 topic info /telemetry/position --verbose --no-daemon --spin-time 2
ros2 topic info /telemetry/battery --verbose --no-daemon --spin-time 2
```

| Publisher offer | Gateway request | Observed result |
| --- | --- | --- |
| Reliable | Reliable | Compatible; both signals became healthy. |
| Best effort | Best effort | Compatible; both signals became healthy. |
| Reliable | Best effort | Compatible; both signals became healthy. |
| Best effort | Reliable | Incompatible; both topics reported a `RELIABILITY` warning and the gateway received neither signal. |

ROS 2 matches requested QoS against what a publisher offers. A reliable
publisher can satisfy a best-effort subscriber, but a best-effort publisher
cannot satisfy a subscriber that requires reliable delivery. On this healthy
local setup, the matched reliable and best-effort runs both delivered position
and battery normally. The experiment demonstrates endpoint compatibility, not
packet loss behavior under an impaired network.

## What I learned

- RAII is less about remembering to free memory and more about making ownership
  obvious. Most gateway state can be held by value; shared ownership is limited
  to the places where `rclcpp` requires it.
- A class template such as `SignalTracker<Value>` keeps the position and
  battery rules in one type-safe model. Its implementation stays in the header
  so each translation unit can instantiate the required concrete type.
- I initially assumed that choosing the newest language standard would be
  better. Selecting C++20 based on the target ROS 2 distribution and compiler
  was the better engineering choice; ecosystem support matters more than using
  C++23 for its own sake.
- The single-threaded executor is a concurrency decision, not an incidental
  default. Writing that assumption down makes a tracker without internal locks
  safe here and makes the work required for a future executor change visible.
- Source timestamps explain when measurements were produced, but monotonic
  receipt age is the safer basis for detecting whether updates have stopped.
- Logging state transitions is more useful than repeating the same stale
  warning on every timer tick. It makes failures visible without log noise.
- QoS reliability follows an offered/requested model. Compatible reliable and
  best-effort runs looked the same on a healthy local machine, while the
  incompatible pairing rejected delivery before network quality mattered.
- Periodic telemetry can often favor the newest sample over retransmitting an
  older one. Commands commonly need reliable delivery plus IDs,
  acknowledgements, timeouts, expiry, and idempotency; reliable DDS delivery
  alone does not prove that a robot executed a command.

## What this demonstrates

The C++ part of this repository represents introductory hands-on experience:
one focused `rclcpp` node, a ROS-independent template model, message conversion,
CMake, formatting, and GoogleTest. It is not a claim of advanced C++, hard
real-time, or performance-engineering expertise.

The senior-engineering signal is the way the change was delivered: a tagged
baseline, explicit invariants, deterministic tests, a stable cross-language
contract, parity before cutover, small reviewable slices, and removal of the
temporary duplicate after the migration was proven.

## Deliberately out of scope

- HTTP or WebSocket forwarding
- A fleet backend or persistent database
- Robot command handling
- Custom ROS messages
- Authentication or encryption configuration
- Retry queues or offline buffering
- Multi-robot discovery
- Production deployment and dashboards
- Hard real-time guarantees or performance claims
- Custom allocators, lock-free structures, or manual memory management

These exclusions keep the repository focused on one complete, reproducible ROS
telemetry path rather than a partial production platform.

## About

This project is part of my exploration of robotics-platform engineering. More
about my background and related work is available at [mrza.ch](https://mrza.ch/).

## License

This project is available under the [MIT License](LICENSE).
