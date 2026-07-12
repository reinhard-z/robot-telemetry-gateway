FROM ros:lyrical-ros-base-resolute

# Keep the C++ formatting check reproducible inside the development image.
RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive \
        apt-get install --yes --no-install-recommends clang-format \
    && rm -rf /var/lib/apt/lists/*

# Keep the mounted ROS workspace at the conventional colcon location.
WORKDIR /workspace

CMD ["bash"]
