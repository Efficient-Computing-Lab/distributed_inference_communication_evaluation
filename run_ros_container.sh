#!/usr/bin/env bash
# Start the ROS 2 Jazzy container used for the ROS 2 benchmarks, with this repo
# mounted at /ros_comm_test. Runs as the calling user (also under sudo), so result
# files stay owned by you and `git pull` can still write into the result folders.
#
#     ./run_ros_container.sh          # laptop
#     sudo ./run_ros_container.sh     # Jetson, where docker needs sudo
set -euo pipefail

REPO="$(cd "$(dirname "$0")" && pwd)"
IMAGE="${IMAGE:-ros:jazzy-ros-base}"
uid="${SUDO_UID:-$(id -u)}"
gid="${SUDO_GID:-$(id -g)}"

extra=()
# JetPack 4's Docker is too old for the syscalls Ubuntu 24.04 images make
if [ -f /etc/nv_tegra_release ]; then
    extra+=(--security-opt seccomp=unconfined)
fi

# HOME=/tmp: the user has no home in the image, and ROS 2 writes logs to ~/.ros
exec docker run -it --rm --network host --ipc host \
    --user "$uid:$gid" -e HOME=/tmp \
    ${extra[@]+"${extra[@]}"} \
    -v "$REPO:/ros_comm_test" -w /ros_comm_test \
    "$IMAGE" bash
