FROM ros:jazzy-ros-base-noble

# Keep the mounted ROS workspace at the conventional colcon location.
WORKDIR /workspace

CMD ["bash"]
