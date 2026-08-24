import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import os

# =========================
# OUTPUT DIRECTORY
# =========================
out_dir = ("plots_2nd/same_machine")
os.makedirs(out_dir, exist_ok=True)

# =========================
# LOAD DATA
# =========================
uint8_file = "../uint8multiarray_list_numpy_array/wifi/same_machine/subscriber_log.csv"
string_file = "../string_list_numpy_array/wifi/same_machine/subscriber_log.csv"

uint8 = pd.read_csv(uint8_file)
string = pd.read_csv(string_file)

# =========================
# CLEAN & FILTER DATA
# =========================
# Convert to numeric (turns 'e+306' strings into float objects)
uint8["latency_sec"] = pd.to_numeric(uint8["latency_sec"], errors="coerce")
string["latency_sec"] = pd.to_numeric(string["latency_sec"], errors="coerce")

# CRITICAL FIX: Filter outliers.
# This removes the corrupted bits (10^306) and the 55-year bug (1.7e9).
# We keep only realistic data between 0 and 5 seconds.
#uint8 = uint8[(uint8["latency_sec"] > 0.0001) & (uint8["latency_sec"] < 5.0)].copy()
#string = string[(string["latency_sec"] > 0.0001) & (string["latency_sec"] < 5.0)].copy()

# Drop any remaining NaNs
uint8 = uint8.dropna(subset=["latency_sec"])
string = string.dropna(subset=["latency_sec"])

# =========================
# 1. LATENCY vs MSG ID
# =========================
plt.figure(figsize=(10, 6))
plt.plot(uint8["msg_id"], uint8["latency_sec"], marker='o', linestyle='-', markersize=4, label="UInt8MultiArray (Binary)")
plt.plot(string["msg_id"], string["latency_sec"], marker='s', linestyle='-', markersize=4, label="String (Base64)")
plt.xlabel("Message ID")
plt.ylabel("Latency (sec)")
plt.title("Latency vs Message ID (Filtered Data)")
plt.legend()
plt.grid(True, which="both", ls="-", alpha=0.5)

plt.savefig(f"{out_dir}/latency_vs_msg_id.png", dpi=300, bbox_inches="tight")
plt.close()

# =========================
# 2. HISTOGRAM
# =========================
plt.figure(figsize=(10, 6))
# Using a fixed range (0.5 to 2.0) helps align the bars for better comparison
plt.hist(uint8["latency_sec"], bins=30, alpha=0.6, label="UInt8MultiArray")
plt.hist(string["latency_sec"], bins=30, alpha=0.6, label="String(Base64)")
plt.xlabel("Latency (sec)")
plt.ylabel("Frequency")
plt.title("Latency Distribution (Comparison)")
plt.legend()
plt.grid(axis='y', alpha=0.3)

plt.savefig(f"{out_dir}/latency_histogram.png", dpi=300, bbox_inches="tight")
plt.close()

# =========================
# 3. BOX PLOT
# =========================
plt.figure(figsize=(8, 6))
plt.boxplot(
    [uint8["latency_sec"], string["latency_sec"]],
    labels=["UInt8MultiArray", "String(Base64)"],
    patch_artist=True,
    medianprops=dict(color="black", linewidth=2),
    boxprops=dict(alpha=0.7)
)
plt.ylabel("Latency (sec)")
plt.title("Latency Comparison (Lower is Better)")
plt.grid(axis='y', linestyle='--', alpha=0.7)

plt.savefig(f"{out_dir}/latency_boxplot.png", dpi=300, bbox_inches="tight")
plt.close()

# =========================
# 4. CDF PLOT
# =========================
def plot_cdf(data, label):
    data_sorted = np.sort(data)
    y = np.arange(1, len(data_sorted) + 1) / len(data_sorted)
    plt.plot(data_sorted, y, label=label, linewidth=2)

plt.figure(figsize=(10, 6))
plot_cdf(uint8["latency_sec"], "UInt8MultiArray")
plot_cdf(string["latency_sec"], "String(Base64)")
plt.xlabel("Latency (sec)")
plt.ylabel("CDF (Probability)")
plt.title("Cumulative Distribution of Latency")
plt.legend()
plt.grid(True, alpha=0.3)

plt.savefig(f"{out_dir}/latency_cdf.png", dpi=300, bbox_inches="tight")
plt.close()

print(f"✅ Success! Charts saved to the /{out_dir} folder.")
print(f"UInt8 Avg: {uint8['latency_sec'].mean():.4f}s")
print(f"String Avg: {string['latency_sec'].mean():.4f}s")

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
_MARKERS = ['o', 's', '^', 'D']


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

# ── Single 150 MB array ──────────────────────────────────────────────────────
# Note the folder asymmetry: the ROS 2 single-array runs use "diff_machine"
# (singular) while BabyROS was collected as "diff_machines" (plural).
babyros_plots(
    "wifi/plots_babyros/x86_machines",
    [(f"{REPO}/uint8multiarray/wifi/x86_machines/subscriber_log.csv", "UInt8MultiArray (Binary)"),
     (f"{REPO}/string/wifi/x86_machines/subscriber_log.csv",          "String (Base64)"),
     (f"{REPO}/babyros/wifi/x86_machines/subscriber_log.csv",         "BabyROS (Zenoh)")],
    "X86 + X86, WiFi, 150 MB array",
)

babyros_plots(
    "wifi/plots_babyros/diff_machines",
    [(f"{REPO}/uint8multiarray/wifi/diff_machine/subscriber_log.csv", "UInt8MultiArray (Binary)"),
     (f"{REPO}/string/wifi/diff_machine/subscriber_log.csv",          "String (Base64)"),
     (f"{REPO}/babyros/wifi/diff_machines/subscriber_log.csv",        "BabyROS (Zenoh)")],
    "X86 + Jetson Nano, WiFi, 150 MB array",
)

# ── List of arrays ───────────────────────────────────────────────────────────
for pair, subtitle in [("x86_machines",  "X86 + X86, WiFi, list of arrays"),
                       ("diff_machines", "X86 + Jetson Nano, WiFi, list of arrays")]:
    babyros_plots(
        f"wifi/plots_babyros_2nd/{pair}",
        [(f"{REPO}/uint8multiarray_list_numpy_array/wifi/{pair}/subscriber_log.csv", "UInt8MultiArray (Binary)"),
         (f"{REPO}/string_list_numpy_array/wifi/{pair}/subscriber_log.csv",          "String (Base64)"),
         (f"{REPO}/babyros_list_numpy_array/wifi/{pair}/subscriber_log.csv",         "BabyROS (Zenoh)")],
        subtitle,
    )
