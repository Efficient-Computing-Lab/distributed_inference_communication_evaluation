"""Launch one benchmark run.

Picks the right interpreter for the method, adds the flags that method needs,
clears the previous CSV so runs are never spliced together, and prints which
side has to start first.

    python3 collect.py sender   arrow_flight ethernet/x86_machines
    python3 collect.py receiver arrow_flight ethernet/x86_machines --peer 147.102.19.196

Use the same folder on both machines. Stop with Ctrl-C after ~100 messages
(about 10 minutes).

Start order is not the same for every method, because whichever side opens the
network port has to be up first:

    Arrow / gRPC   sender first    receiver needs --peer <sender ip>
    ROS 2          receiver first  no --peer, both sides share ROS_DOMAIN_ID
    BabyROS        receiver first  sender needs --peer <receiver ip>
                                   (optional, Zenoh usually finds the peer)
"""

import argparse
import os
import shutil
import subprocess
import sys


CONDA_BASE = os.environ.get("CONDA_BASE", "/home/gkorod/miniconda3")
ROS_SETUP = os.environ.get("ROS_SETUP", "/opt/ros/jazzy/setup.bash")

# env, sender script, receiver script, port, sender csv, receiver csv
METHODS = {
    "string":                           ("ros2", "publisher.py", "subscriber.py", None,  "publisher_log.csv", "subscriber_log.csv"),
    "uint8multiarray":                  ("ros2", "publisher.py", "subscriber.py", None,  "publisher_log.csv", "subscriber_log.csv"),
    "string_list_numpy_array":          ("ros2", "publisher.py", "subscriber.py", None,  "publisher_log.csv", "subscriber_log.csv"),
    "uint8multiarray_list_numpy_array": ("ros2", "publisher.py", "subscriber.py", None,  "publisher_log.csv", "subscriber_log.csv"),
    "babyros":                          ("babyros", "publisher.py", "subscriber.py", None, "publisher_log.csv", "subscriber_log.csv"),
    "babyros_list_numpy_array":         ("babyros", "publisher.py", "subscriber.py", None, "publisher_log.csv", "subscriber_log.csv"),
    "babyros_client_server":            ("babyros", "server.py", "client.py", None,      "server_log.csv", "client_log.csv"),
    "arrow_flight":                     ("arrow_flight_env", "server.py", "client.py", 8815,  "server_log.csv", "client_log.csv"),
    "arrow_flight_list_numpy_array":    ("arrow_flight_env", "server.py", "client.py", 8815,  "server_log.csv", "client_log.csv"),
    "arrow_ipc":                        ("arrow_flight_env", "server.py", "client.py", 9000,  "server_log.csv", "client_log.csv"),
    "arrow_ipc_list_numpy_array":       ("arrow_flight_env", "server.py", "client.py", 9000,  "server_log.csv", "client_log.csv"),
    "grpc_string":                      ("grpc_env", "server.py", "client.py", 50051, "publisher_log.csv", "subscriber_log.csv"),
    "grpc_string_list_numpy_array":     ("grpc_env", "server.py", "client.py", 50051, "server_log.csv", "client_log.csv"),
    "tcp_raw":                          ("arrow_flight_env", "server.py", "client.py", 9000, "server_log.csv", "client_log.csv"),
}

# whichever side opens the port must start first
FIRST_SIDE = {"arrow_flight_env": "sender", "grpc_env": "sender"}


def main():
    parser = argparse.ArgumentParser(
        description="Launch one benchmark run.",
        epilog="methods: " + ", ".join(sorted(METHODS)),
    )
    parser.add_argument("role", choices=["sender", "receiver"])
    parser.add_argument("method", help="benchmark directory, e.g. arrow_flight")
    parser.add_argument("folder", help="results folder, e.g. ethernet/x86_machines")
    parser.add_argument("--peer", default=None,
                        help="the other machine's IP — needed by the receiver for "
                             "Arrow/gRPC, by the sender for BabyROS")
    parser.add_argument("--keep", action="store_true",
                        help="append to the existing CSV instead of replacing it "
                             "(normally you want a clean file)")
    args = parser.parse_args()

    if args.method not in METHODS:
        parser.error(f"unknown method '{args.method}'\nknown: " + ", ".join(sorted(METHODS)))

    env, sender_script, receiver_script, port, sender_csv, receiver_csv = METHODS[args.method]
    script = sender_script if args.role == "sender" else receiver_script
    csv_name = sender_csv if args.role == "sender" else receiver_csv

    root = os.path.dirname(os.path.abspath(__file__))
    workdir = os.path.join(root, args.method)
    if not os.path.isdir(workdir):
        sys.exit(f"no such directory: {workdir}")

    out = os.path.join(workdir, args.folder)
    os.makedirs(out, exist_ok=True)
    csv_path = os.path.join(out, csv_name)
    if os.path.exists(csv_path) and not args.keep:
        print(f"removing previous {args.method}/{args.folder}/{csv_name}")
        os.remove(csv_path)

    cmd_args = ["--folder", args.folder]
    if port is not None:
        cmd_args += ["--port", str(port)]
    if env == "babyros":
        # Zenoh: the receiver listens, the sender dials it
        if args.role == "receiver":
            cmd_args += ["--listen", "tcp/0.0.0.0:7447"]
        elif args.peer:
            cmd_args += ["--connect", f"tcp/{args.peer}:7447"]
    elif env != "ros2" and args.role == "receiver" and args.peer:
        cmd_args += ["--host", args.peer]

    if env == "ros2":
        if not os.path.exists(ROS_SETUP):
            sys.exit(f"ROS 2 setup not found at {ROS_SETUP} (override with ROS_SETUP=...)")
        os.environ.setdefault("ROS_DOMAIN_ID", "0")
        inner = " ".join(["python3", "-u", script] + cmd_args)
        cmd = ["bash", "-c", f'source "{ROS_SETUP}" && exec {inner}']
        shown = f"python3 {script} {' '.join(cmd_args)}"
        print(f"ROS 2 sourced, ROS_DOMAIN_ID={os.environ['ROS_DOMAIN_ID']}")
    else:
        python = os.path.join(CONDA_BASE, "envs", env, "bin", "python")
        if not os.access(python, os.X_OK):
            sys.exit(f"env '{env}' not found at {python} (override with CONDA_BASE=...)")
        cmd = [python, "-u", script] + cmd_args
        shown = f"{script} {' '.join(cmd_args)}"
        print(f"using env: {env}")

    first = FIRST_SIDE.get(env, "receiver")
    print(f"run: {args.method}/{shown}")
    if args.role == first:
        print("start order: this side goes FIRST — start the other side once this is up")
    else:
        print(f"start order: the {first} must already be running, or this will fail to connect")
    print("Ctrl-C to stop (~100 messages, about 10 min)\n")

    try:
        sys.exit(subprocess.call(cmd, cwd=workdir))
    except KeyboardInterrupt:
        sys.exit(0)


if __name__ == "__main__":
    main()
