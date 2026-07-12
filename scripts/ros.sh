#!/usr/bin/env bash

set -euo pipefail

readonly script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
readonly repository_root="$(cd -- "${script_dir}/.." && pwd)"
readonly image="${ROBOT_TELEMETRY_IMAGE:-robot-telemetry-gateway:lyrical}"

docker_arguments=(
  --rm
  --init
  # Colcon recursively discovers the ROS packages inside this repository.
  --volume "${repository_root}:/workspace/src/robot_telemetry_gateway"
  --workdir /workspace
)

# Allocate a terminal only for interactive use so the script also works in CI.
if [[ -t 0 && -t 1 ]]; then
  docker_arguments+=(--interactive --tty)
fi

if [[ $# -eq 0 ]]; then
  set -- bash
fi

exec docker run "${docker_arguments[@]}" "${image}" "$@"
