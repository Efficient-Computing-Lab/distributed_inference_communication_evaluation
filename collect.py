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

ROS 2 methods take --transport udp|tcp (default udp, which is what the recorded
ethernet/ and wifi/ results used). tcp loads the pure-TCP Fast DDS profiles in
fastdds_tcp/ (discovery and data over one TCP connection, no UDP): the receiver
listens on port 5100, the sender connects to --peer. The profile actually used,
with the peer filled in, is saved next to the CSVs. TCP results must go to a
folder whose top level ends in _tcp, e.g.

    python3 collect.py receiver uint8multiarray ethernet_tcp/x86_machines --transport tcp
    python3 collect.py sender   uint8multiarray ethernet_tcp/x86_machines --transport tcp --peer <receiver ip>
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

ROS2_TRANSPORTS = ("udp", "tcp")

# Pure-TCP Fast DDS profiles for --transport tcp, per role. The sender's names the
# receiver's address, which is replaced with --peer.
TCP_PROFILES = {"receiver": "fastdds_tcp/receiver_tcp.xml",
                "sender": "fastdds_tcp/sender_tcp.xml"}
TCP_PEER_ADDRESS = "<address>147.102.19.151</address>"

# The profiles ask for 256 MB socket buffers; Linux silently clamps them to these
# limits, which would bring back the deadlock the large buffers avoid.
TCP_BUFFER_BYTES = 268435456
SOCKET_LIMITS = ("/proc/sys/net/core/wmem_max", "/proc/sys/net/core/rmem_max")

# environment captured next to the CSVs so the transport of a run is on record
RECORDED_ENV = ("RMW_IMPLEMENTATION", "FASTDDS_BUILTIN_TRANSPORTS",
                "FASTRTPS_DEFAULT_PROFILES_FILE", "ROS_DOMAIN_ID", "ROS_STATIC_PEERS")


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
                             "Arrow/gRPC, by the sender for BabyROS; optional for "
                             "ROS 2 (unicast discovery via ROS_STATIC_PEERS)")
    parser.add_argument("--keep", action="store_true",
                        help="append to the existing CSV instead of replacing it "
                             "(normally you want a clean file)")
    parser.add_argument("--transport", choices=ROS2_TRANSPORTS, default="udp",
                        help="ROS 2 methods only: udp (stock Fast DDS) or tcp "
                             "(pure-TCP profiles in fastdds_tcp/; the sender needs --peer)")
    args = parser.parse_args()

    if args.method not in METHODS:
        parser.error(f"unknown method '{args.method}'\nknown: " + ", ".join(sorted(METHODS)))

    env, sender_script, receiver_script, port, sender_csv, receiver_csv = METHODS[args.method]

    # keep TCP and UDP results in separate folders so neither overwrites the other
    top, _, rest = args.folder.strip("/").partition("/")
    tcp_folder = top.endswith("_tcp")
    if env != "ros2" and args.transport != "udp":
        parser.error("--transport only applies to the ROS 2 methods")
    if args.transport == "tcp" and not tcp_folder:
        parser.error(f"--transport tcp needs a *_tcp folder, e.g. "
                     f"{'/'.join(filter(None, [top + '_tcp', rest]))}")
    if env == "ros2" and args.transport == "udp" and tcp_folder:
        parser.error(f"'{args.folder}' is a TCP results folder; add --transport tcp")
    if args.transport == "tcp":
        if args.role == "sender" and not args.peer:
            parser.error("--transport tcp: the sender needs --peer <receiver ip>")
        for path in SOCKET_LIMITS:
            with open(path) as f:
                if int(f.read()) < TCP_BUFFER_BYTES:
                    sys.exit(f"{path} is below {TCP_BUFFER_BYTES}; raise it on this host first:\n"
                             f"  sudo sysctl -w net.core.wmem_max={TCP_BUFFER_BYTES} "
                             f"net.core.rmem_max={TCP_BUFFER_BYTES}")

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
        os.environ["RMW_IMPLEMENTATION"] = "rmw_fastrtps_cpp"
        # a profile or builtin-transport setting left in the shell must not change
        # a recorded run, so only what is set below applies
        if os.environ.pop("FASTRTPS_DEFAULT_PROFILES_FILE", None):
            print("ignoring FASTRTPS_DEFAULT_PROFILES_FILE from the shell")
        os.environ.pop("ROS_STATIC_PEERS", None)
        if args.transport == "udp":
            os.environ["FASTDDS_BUILTIN_TRANSPORTS"] = "DEFAULT"
            # unicast discovery for when multicast doesn't get through (e.g. Docker hosts)
            if args.peer:
                os.environ["ROS_STATIC_PEERS"] = args.peer
        else:
            # the profile disables the builtin transports itself
            os.environ.pop("FASTDDS_BUILTIN_TRANSPORTS", None)
            with open(os.path.join(root, TCP_PROFILES[args.role])) as f:
                profile = f.read()
            if args.role == "sender":
                profile = profile.replace(TCP_PEER_ADDRESS, f"<address>{args.peer}</address>")
            profile_path = os.path.join(out, f"{args.role}_fastdds_tcp.xml")
            with open(profile_path, "w") as f:
                f.write(profile)
            os.environ["FASTRTPS_DEFAULT_PROFILES_FILE"] = profile_path
        with open(os.path.join(out, f"{args.role}_env.txt"), "w") as f:
            for name in RECORDED_ENV:
                f.write(f"{name}={os.environ.get(name, '')}\n")
        inner = " ".join(["python3", "-u", script] + cmd_args)
        cmd = ["bash", "-c", f'source "{ROS_SETUP}" && exec {inner}']
        shown = f"python3 {script} {' '.join(cmd_args)}"
        detail = (f"profile {os.path.relpath(os.environ['FASTRTPS_DEFAULT_PROFILES_FILE'], root)}"
                  if args.transport == "tcp" else "stock Fast DDS")
        print(f"ROS 2 sourced, ROS_DOMAIN_ID={os.environ['ROS_DOMAIN_ID']}, "
              f"transport={args.transport} ({detail})")
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
