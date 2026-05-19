import subprocess
import json
import os
import sys
import time
import argparse
import socket
import platform
from statistics import mean
from datetime import datetime
from get_machine_info import *

def run_iperf(ip, trial_num, output_dir, duration=30):
    logfile = os.path.join(output_dir, f"exp_{trial_num}.json")

    cmd = [
        "iperf3",
        "-c", ip,
        "-t", str(duration),
        "-J",
        "--logfile", logfile
    ]

    print(f"[{trial_num}] Running: {' '.join(cmd)}")

    result = subprocess.run(cmd)

    if result.returncode != 0:
        print(f"[{trial_num}] iperf3 failed.")
        return None

    try:
        with open(logfile, "r") as f:
            data = json.load(f)

        bitrate = data["end"]["sum_received"]["bits_per_second"]

        print(f"[{trial_num}] Bitrate: {bitrate / 1e6:.2f} Mbps")

        return bitrate

    except Exception as e:
        print(f"[{trial_num}] Failed to parse logfile: {e}")
        return None


def main():
    parser = argparse.ArgumentParser(
        description="Repeated iperf3 TCP benchmark"
    )

    parser.add_argument(
        "--ip",
        type=str,
        required=True,
        help="iperf3 server IP"
    )

    parser.add_argument(
        "--remote_user",
        type=str,
        required=True,
        help="remote machine user name"
    )

    parser.add_argument(
        "--trials",
        type=int,
        default=100,
        help="Number of trials"
    )

    parser.add_argument(
        "--duration",
        type=int,
        default=30,
        help="Duration of each trial in seconds"
    )

    args = parser.parse_args()

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    output_dir = f"iperf_outputs/iperf3_tcp_{timestamp}"
    os.makedirs(output_dir, exist_ok=True)

    machine_info = get_machine_info()

    machine_info_path = os.path.join(output_dir, "machine_info_local.json")

    with open(machine_info_path, "w") as f:
        json.dump(machine_info, f, indent=4)

    print("\n===== LOCAL MACHINE INFO =====")
    for k, v in machine_info.items():
        print(f"{k}: {v}")

    cmd = f"ssh {args.remote_user}@{args.ip} 'python3 -' < {os.path.join(os.getcwd(),'get_machine_info.py')}"
    result = subprocess.run(cmd, capture_output=True, text=True, shell=True)
    if result.returncode != 0 or not result.stdout.strip():
        print(f"ERROR: Failed to get remote machine info (exit {result.returncode})")
        print(f"stderr: {result.stderr.strip()}")
        sys.exit(1)
    info_remote = json.loads(result.stdout)
    print("\n===== REMOTE MACHINE INFO =====")
    for k, v in info_remote.items():
        print(f"{k}: {v}")

    with open(os.path.join(output_dir, "machine_info_remote.json"), "w") as f:
        json.dump(info_remote, f, indent=4)

    print(f"Starting iperf3 server on remote host {args.remote_user}@{args.ip}")
    server_cmd = (
        "ssh {user}@{ip} "
        "'nohup iperf3 -s 1> /tmp/iperf3_server.log 2>&1 &'"
    ).format(user=args.remote_user, ip=args.ip)
    subprocess.run(server_cmd, shell=True)
    time.sleep(3)

    all_bitrates = []

    start_time = time.time()

    for i in range(1, args.trials + 1):
        bitrate = run_iperf(
            ip=args.ip,
            trial_num=i,
            output_dir=output_dir,
            duration=args.duration
        )

        if bitrate is not None:
            all_bitrates.append(bitrate)

    elapsed = time.time() - start_time

    print("\n========== RESULTS ==========")

    if all_bitrates:
        avg_bitrate = mean(all_bitrates)

        print(f"Successful trials : {len(all_bitrates)}")
        print(f"Average bitrate   : {avg_bitrate / 1e6:.2f} Mbps")
        print(f"Average bitrate   : {avg_bitrate / 8e6:.2f} MB/s")
        print(f"Min bitrate       : {min(all_bitrates) / 1e6:.2f} Mbps")
        print(f"Max bitrate       : {max(all_bitrates) / 1e6:.2f} Mbps")

        summary = {
            "successful_trials": len(all_bitrates),
            "average_bitrate_bps": avg_bitrate,
            "average_bitrate_mbps": avg_bitrate / 1e6,
            "average_bitrate_MBps": avg_bitrate / 8e6,
            "min_bitrate_mbps": min(all_bitrates) / 1e6,
            "max_bitrate_mbps": max(all_bitrates) / 1e6,
            "total_runtime_sec": elapsed,
            "machine_info": machine_info
        }

        summary_path = os.path.join(output_dir, "summary.json")

        with open(summary_path, "w") as f:
            json.dump(summary, f, indent=4)

        print(f"\nSummary saved to: {summary_path}")

    else:
        print("No successful trials.")

    print(f"Total runtime: {elapsed:.2f} sec")


if __name__ == "__main__":
    main()
