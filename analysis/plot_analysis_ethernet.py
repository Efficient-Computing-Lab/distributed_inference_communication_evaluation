import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import os

BASE = os.path.dirname(os.path.abspath(__file__)) + "/.."

def plot_cdf(data, label):
    data_sorted = np.sort(data)
    y = np.arange(1, len(data_sorted) + 1) / len(data_sorted)
    plt.plot(data_sorted, y, label=label, linewidth=2)


def make_plots(out_dir, df_a, label_a, df_b, label_b, lat_col_a="latency_sec", lat_col_b="latency_sec"):
    os.makedirs(out_dir, exist_ok=True)

    a = pd.to_numeric(df_a[lat_col_a], errors="coerce")
    b = pd.to_numeric(df_b[lat_col_b], errors="coerce")
    a = a.dropna()
    b = b.dropna()

    id_a = df_a["msg_id"].iloc[:len(a)]
    id_b = df_b["msg_id"].iloc[:len(b)]

    # 1. Latency vs msg id
    plt.figure(figsize=(10, 6))
    plt.plot(id_a, a, marker='o', linestyle='-', markersize=4, label=label_a)
    plt.plot(id_b, b, marker='s', linestyle='-', markersize=4, label=label_b)
    plt.xlabel("Message ID")
    plt.ylabel("Latency (sec)")
    plt.title("Latency vs Message ID")
    plt.legend()
    plt.grid(True, which="both", ls="-", alpha=0.5)
    plt.savefig(f"{out_dir}/latency_vs_msg_id.png", dpi=300, bbox_inches="tight")
    plt.close()

    # 2. Histogram
    plt.figure(figsize=(10, 6))
    plt.hist(a, bins=30, alpha=0.6, label=label_a)
    plt.hist(b, bins=30, alpha=0.6, label=label_b)
    plt.xlabel("Latency (sec)")
    plt.ylabel("Frequency")
    plt.title("Latency Distribution (Comparison)")
    plt.legend()
    plt.grid(axis='y', alpha=0.3)
    plt.savefig(f"{out_dir}/latency_histogram.png", dpi=300, bbox_inches="tight")
    plt.close()

    # 3. Box plot
    plt.figure(figsize=(8, 6))
    plt.boxplot(
        [a, b],
        labels=[label_a, label_b],
        patch_artist=True,
        medianprops=dict(color="black", linewidth=2),
        boxprops=dict(alpha=0.7),
    )
    plt.ylabel("Latency (sec)")
    plt.title("Latency Comparison (Lower is Better)")
    plt.grid(axis='y', linestyle='--', alpha=0.7)
    plt.savefig(f"{out_dir}/latency_boxplot.png", dpi=300, bbox_inches="tight")
    plt.close()

    # 4. CDF
    plt.figure(figsize=(10, 6))
    plot_cdf(a, label_a)
    plot_cdf(b, label_b)
    plt.xlabel("Latency (sec)")
    plt.ylabel("CDF (Probability)")
    plt.title("Cumulative Distribution of Latency")
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.savefig(f"{out_dir}/latency_cdf.png", dpi=300, bbox_inches="tight")
    plt.close()

    print(f"Saved plots to {out_dir}")
    print(f"  {label_a} avg: {a.mean():.4f}s")
    print(f"  {label_b} avg: {b.mean():.4f}s")
    return a.mean(), b.mean()


# ── Single array: UInt8MultiArray vs String ──────────────────────────────────
uint8 = pd.read_csv(f"{BASE}/uint8multiarray/ethernet/x86_machines/subscriber_log.csv")
string = pd.read_csv(f"{BASE}/string/ethernet/x86_machines/subscriber_log.csv")
make_plots(
    "ethernet/plots/x86_machines",
    uint8, "UInt8MultiArray (Binary)",
    string, "String (Base64)",
)

uint8_diff = pd.read_csv(f"{BASE}/uint8multiarray/ethernet/diff_machines/subscriber_log.csv")
string_diff = pd.read_csv(f"{BASE}/string/ethernet/diff_machines/subscriber_log.csv")
make_plots(
    "ethernet/plots/diff_machines",
    uint8_diff, "UInt8MultiArray (Binary)",
    string_diff, "String (Base64)",
)

# ── List of arrays: UInt8MultiArray vs String ────────────────────────────────
uint8_list = pd.read_csv(f"{BASE}/uint8multiarray_list_numpy_array/ethernet/x86_machines/subscriber_log.csv")
string_list = pd.read_csv(f"{BASE}/string_list_numpy_array/ethernet/x86_machines/subscriber_log.csv")
make_plots(
    "ethernet/plots_2nd/x86_machines",
    uint8_list, "UInt8MultiArray (Binary)",
    string_list, "String (Base64)",
    lat_col_a="latency",
    lat_col_b="latency",
)

uint8_list_diff = pd.read_csv(f"{BASE}/uint8multiarray_list_numpy_array/ethernet/diff_machines/subscriber_log.csv")
string_list_diff = pd.read_csv(f"{BASE}/string_list_numpy_array/ethernet/diff_machines/subscriber_log.csv")
make_plots(
    "ethernet/plots_2nd/diff_machines",
    uint8_list_diff, "UInt8MultiArray (Binary)",
    string_list_diff, "String (Base64)",
    lat_col_a="latency",
    lat_col_b="latency",
)


def make_non_ros_plots(out_dir, arrow_flight_df, arrow_ipc_df, grpc_string_df):
    os.makedirs(out_dir, exist_ok=True)

    series = [
        (pd.to_numeric(arrow_flight_df["latency_sec"], errors="coerce").dropna(), arrow_flight_df["msg_id"], "Arrow Flight (gRPC)"),
        (pd.to_numeric(arrow_ipc_df["latency_sec"],    errors="coerce").dropna(), arrow_ipc_df["msg_id"],    "Arrow IPC + TCP"),
        (pd.to_numeric(grpc_string_df["latency_sec"],  errors="coerce").dropna(), grpc_string_df["msg_id"],  "gRPC String (bytes)"),
    ]

    markers = ['o', 's', '^']

    plt.figure(figsize=(10, 6))
    for (lat, ids, label), marker in zip(series, markers):
        plt.plot(ids, lat, marker=marker, linestyle='-', markersize=4, label=label)
    plt.xlabel("Message ID"); plt.ylabel("Latency (sec)")
    plt.title("Latency vs Message ID — Non-ROS Methods")
    plt.legend(); plt.grid(True, which="both", ls="-", alpha=0.5)
    plt.savefig(f"{out_dir}/latency_vs_msg_id.png", dpi=300, bbox_inches="tight")
    plt.close()

    plt.figure(figsize=(10, 6))
    for lat, _, label in series:
        plt.hist(lat, bins=30, alpha=0.6, label=label)
    plt.xlabel("Latency (sec)"); plt.ylabel("Frequency")
    plt.title("Latency Distribution — Non-ROS Methods")
    plt.legend(); plt.grid(axis='y', alpha=0.3)
    plt.savefig(f"{out_dir}/latency_histogram.png", dpi=300, bbox_inches="tight")
    plt.close()

    plt.figure(figsize=(8, 6))
    plt.boxplot(
        [lat for lat, _, _ in series],
        tick_labels=[label for _, _, label in series],
        patch_artist=True,
        medianprops=dict(color="black", linewidth=2),
        boxprops=dict(alpha=0.7),
    )
    plt.ylabel("Latency (sec)"); plt.title("Latency Comparison — Non-ROS Methods (Lower is Better)")
    plt.grid(axis='y', linestyle='--', alpha=0.7)
    plt.savefig(f"{out_dir}/latency_boxplot.png", dpi=300, bbox_inches="tight")
    plt.close()

    plt.figure(figsize=(10, 6))
    for lat, _, label in series:
        data_sorted = np.sort(lat)
        y = np.arange(1, len(data_sorted) + 1) / len(data_sorted)
        plt.plot(data_sorted, y, label=label, linewidth=2)
    plt.xlabel("Latency (sec)"); plt.ylabel("CDF (Probability)")
    plt.title("Cumulative Distribution of Latency — Non-ROS Methods")
    plt.legend(); plt.grid(True, alpha=0.3)
    plt.savefig(f"{out_dir}/latency_cdf.png", dpi=300, bbox_inches="tight")
    plt.close()

    print(f"Saved plots to {out_dir}")
    for lat, _, label in series:
        print(f"  {label} avg: {lat.mean():.4f}s")


# ── Non-ROS comparison: Arrow IPC vs Arrow Flight vs gRPC String ─────────────
make_non_ros_plots(
    "ethernet/plots_non_ros/x86_machines",
    pd.read_csv(f"{BASE}/arrow_flight/ethernet/x86_machines/client_log.csv"),
    pd.read_csv(f"{BASE}/arrow_ipc/ethernet/x86_machines/client_log.csv"),
    pd.read_csv(f"{BASE}/grpc_string/ethernet/x86_machines/subscriber_log.csv"),
)

make_non_ros_plots(
    "ethernet/plots_non_ros/diff_machines",
    pd.read_csv(f"{BASE}/arrow_flight/ethernet/diff_machines/client_log.csv"),
    pd.read_csv(f"{BASE}/arrow_ipc/ethernet/diff_machines/client_log.csv"),
    pd.read_csv(f"{BASE}/grpc_string/ethernet/diff_machines/subscriber_log.csv"),
)


# ============================================================================
# BabyROS (Zenoh) vs the ROS 2 methods
# ============================================================================
# Self-contained N-series helper. The pairwise plotting above is hard-wired to
# exactly two dataframes and this comparison needs three. It also auto-detects
# the latency column: this repo uses "latency_sec" in some CSVs and "latency"
# in others, and the two are not consistent between the wifi and ethernet runs
# of the same method. Configurations that were never collected are skipped
# rather than raising, so the script still runs on a partial dataset.

REPO = os.path.dirname(os.path.abspath(__file__)) + "/.."
_LAT_COLS = ("latency_sec", "latency")
_MARKERS = ['o', 's', '^', 'D', 'v', 'P']


def _load_run(path, label):
    if not os.path.exists(path):
        print(f"  skip {label}: {os.path.relpath(path, REPO)} not collected")
        return None
    df = pd.read_csv(path)
    col = next((c for c in _LAT_COLS if c in df.columns), None)
    if col is None:
        print(f"  skip {label}: no latency column")
        return None
    lat = pd.to_numeric(df[col], errors="coerce").dropna()
    return lat, df["msg_id"].iloc[:len(lat)], label


def babyros_plots(out_dir, entries, subtitle):
    runs = [r for r in (_load_run(p, l) for p, l in entries) if r is not None]
    if len(runs) < 2:
        print(f"  not enough data for {out_dir} — skipped\n")
        return
    os.makedirs(out_dir, exist_ok=True)

    plt.figure(figsize=(10, 6))
    for (lat, ids, label), mk in zip(runs, _MARKERS):
        plt.plot(ids, lat, marker=mk, linestyle='-', markersize=4, label=label)
    plt.xlabel("Message ID"); plt.ylabel("Latency (sec)")
    plt.title(f"Latency vs Message ID — {subtitle}")
    plt.legend(); plt.grid(True, which="both", ls="-", alpha=0.5)
    plt.savefig(f"{out_dir}/latency_vs_msg_id.png", dpi=300, bbox_inches="tight")
    plt.close()

    plt.figure(figsize=(10, 6))
    for lat, _, label in runs:
        plt.hist(lat, bins=30, alpha=0.6, label=label)
    plt.xlabel("Latency (sec)"); plt.ylabel("Frequency")
    plt.title(f"Latency Distribution — {subtitle}")
    plt.legend(); plt.grid(axis='y', alpha=0.3)
    plt.savefig(f"{out_dir}/latency_histogram.png", dpi=300, bbox_inches="tight")
    plt.close()

    plt.figure(figsize=(8, 6))
    plt.boxplot([lat for lat, _, _ in runs],
                tick_labels=[label for _, _, label in runs],
                patch_artist=True,
                medianprops=dict(color="black", linewidth=2),
                boxprops=dict(alpha=0.7))
    plt.ylabel("Latency (sec)")
    plt.title(f"Latency Comparison — {subtitle}")
    plt.xticks(rotation=12)
    plt.grid(axis='y', linestyle='--', alpha=0.7)
    plt.savefig(f"{out_dir}/latency_boxplot.png", dpi=300, bbox_inches="tight")
    plt.close()

    plt.figure(figsize=(10, 6))
    for lat, _, label in runs:
        srt = np.sort(lat)
        plt.plot(srt, np.arange(1, len(srt) + 1) / len(srt), label=label, linewidth=2)
    plt.xlabel("Latency (sec)"); plt.ylabel("CDF (Probability)")
    plt.title(f"Cumulative Distribution of Latency — {subtitle}")
    plt.legend(); plt.grid(True, alpha=0.3)
    plt.savefig(f"{out_dir}/latency_cdf.png", dpi=300, bbox_inches="tight")
    plt.close()

    print(f"Saved plots to {out_dir}")
    for lat, _, label in runs:
        print(f"  {label:26} avg={lat.mean():8.4f}s  std={lat.std():.4f}  n={len(lat)}")
    print()

# ── All six methods, single 150 MB array ─────────────────────────────────────
for pair, sub in [("x86_machines",  "X86 + X86, Ethernet, one 150 MB block"),
                  ("diff_machines", "X86 + Jetson Nano, Ethernet, one 150 MB block")]:
    babyros_plots(
        f"ethernet/plots_all/{pair}",
        [(f"{REPO}/arrow_ipc/ethernet/{pair}/client_log.csv",           "Arrow IPC + TCP"),
         (f"{REPO}/arrow_flight/ethernet/{pair}/client_log.csv",        "Arrow Flight (gRPC)"),
         (f"{REPO}/babyros/ethernet/{pair}/subscriber_log.csv",         "BabyROS (Zenoh)"),
         (f"{REPO}/uint8multiarray/ethernet/{pair}/subscriber_log.csv", "ROS2 UInt8MultiArray"),
         (f"{REPO}/grpc_string/ethernet/{pair}/subscriber_log.csv",     "gRPC String (bytes)"),
         (f"{REPO}/string/ethernet/{pair}/subscriber_log.csv",          "ROS2 String (Base64)")],
        sub,
    )

# ── All six methods, four blocks totalling 98.84 MB ──────────────────────────
for pair, sub in [("x86_machines",  "X86 + X86, Ethernet, four blocks"),
                  ("diff_machines", "X86 + Jetson Nano, Ethernet, four blocks")]:
    babyros_plots(
        f"ethernet/plots_all_2nd/{pair}",
        [(f"{REPO}/arrow_ipc_list_numpy_array/ethernet/{pair}/client_log.csv",              "Arrow IPC + TCP"),
         (f"{REPO}/arrow_flight_list_numpy_array/ethernet/{pair}/client_log.csv",           "Arrow Flight (gRPC)"),
         (f"{REPO}/babyros_list_numpy_array/ethernet/{pair}/subscriber_log.csv",            "BabyROS (Zenoh)"),
         (f"{REPO}/grpc_string_list_numpy_array/ethernet/{pair}/client_log.csv",            "gRPC (repeated bytes)"),
         (f"{REPO}/string_list_numpy_array/ethernet/{pair}/subscriber_log.csv",             "ROS2 String (Base64)"),
         (f"{REPO}/uint8multiarray_list_numpy_array/ethernet/{pair}/subscriber_log.csv",    "ROS2 UInt8MultiArray")],
        sub,
    )
