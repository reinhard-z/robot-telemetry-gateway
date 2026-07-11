# Robot Telemetry Gateway

A small Python and ROS 2 project demonstrating telemetry freshness,
stale-signal recovery, and QoS trade-offs at the robot-to-platform boundary.

> **Status:** Initial project setup. The ROS 2 implementation is in progress.

## Why this project exists

I am building this project to deepen my hands-on Python and ROS 2 experience
while applying the production engineering practices I use in Java and
TypeScript systems.

The focus is deliberately narrow: build one understandable, tested telemetry
path and explore how it behaves when sensor updates stop and recover.

## Planned architecture

```text
ROS 2 simulator node
  ├── position telemetry (1 Hz)
  └── battery telemetry  (1 Hz)
              │
              ▼
Python gateway node
  ├── records measurement and receipt times
  ├── tracks signal freshness independently
  └── logs healthy, stale, and recovered transitions
```

The simulator will pause individual signals on a deterministic schedule so
stale detection and recovery can be demonstrated without external hardware.

## Project goals

- Write clear, typed, idiomatic Python.
- Keep ROS 2 integration separate from testable domain logic.
- Compare reliable and best-effort ROS 2 QoS policies.
- Explain why telemetry and robot commands may need different delivery
  semantics.
- Provide a short, reproducible local demonstration and automated tests.

## How to run

Build and run instructions will be added with the first working ROS 2 slice.

## Deliberately out of scope

- HTTP or WebSocket forwarding
- A fleet backend or persistent database
- Robot command handling
- Custom ROS messages
- Multi-robot discovery
- Production deployment and dashboards

Networking may be explored later, but only after the local ROS 2 pipeline is
working and tested.

## About

This project is part of my exploration of robotics-platform engineering. More
about my background and related work is available at [mrza.ch](https://mrza.ch/).
