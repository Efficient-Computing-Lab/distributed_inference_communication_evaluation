import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import os

# =========================
# OUTPUT DIRECTORY
# =========================
out_dir = ("plots/diff_machine")
os.makedirs(out_dir, exist_ok=True)

# =========================
# LOAD DATA
# =========================
uint8_file = "../uint8multiarray/diff_machine/subscriber_log.csv"
string_file = "../string/diff_machine/subscriber_log.csv"

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