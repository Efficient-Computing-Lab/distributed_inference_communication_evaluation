"""Paper figures: latency box plots for the four Ethernet configurations.

Writes figures/{first,second,third,fourth}_figure.{png,pdf}:
    first  = single 150 MB array, x86 receiver
    second = single 150 MB array, Jetson Nano receiver
    third  = four arrays (98.8 MB), x86 receiver
    fourth = four arrays (98.8 MB), Jetson Nano receiver

All four panels share one method order and one latency axis, so x86 vs Jetson and
single vs four arrays can be compared by position alone.

    python3 paper/make_figures.py
"""
import os

import matplotlib.pyplot as plt
import pandas as pd

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(REPO, "paper", "figures")

# Top-to-bottom order, matching the per-technology subsections of the paper.
# (label, single-array dir, four-array dir, receiver log, is_ros2)
METHODS = [
    ("Arrow IPC + TCP", "arrow_ipc", "arrow_ipc_list_numpy_array", "client_log.csv", False),
    ("Arrow Flight", "arrow_flight", "arrow_flight_list_numpy_array", "client_log.csv", False),
    ("BabyROS (Zenoh)", "babyros", "babyros_list_numpy_array", "subscriber_log.csv", False),
    ("gRPC", "grpc_string", "grpc_string_list_numpy_array", None, False),
    ("ROS 2 UInt8MultiArray", "uint8multiarray", "uint8multiarray_list_numpy_array", "subscriber_log.csv", True),
    ("ROS 2 String (Base64)", "string", "string_list_numpy_array", "subscriber_log.csv", True),
]

PANELS = [
    ("first_figure", False, "x86_machines"),
    ("second_figure", False, "diff_machines"),
    ("third_figure", True, "x86_machines"),
    ("fourth_figure", True, "diff_machines"),
]

# Reference palette, categorical slots 1-2 (light mode).
NON_ROS = "#2a78d6"
ROS2 = "#eb6834"
INK = "#0b0b0b"
INK_2 = "#52514e"
GRID = "#e4e3df"

XLIM = (0.9, 5.5)
XTICKS = [1, 2, 3, 4, 5]


def receiver_log(method_dir, log, pair):
    folder = os.path.join(REPO, method_dir, "ethernet", pair)
    # gRPC names its receiver log differently in the two payload variants.
    candidates = [log] if log else ["subscriber_log.csv", "client_log.csv"]
    for name in candidates:
        path = os.path.join(folder, name)
        if os.path.exists(path):
            return path
    raise FileNotFoundError(f"no receiver log in {folder}")


def latencies(path):
    df = pd.read_csv(path)
    col = "latency_sec" if "latency_sec" in df.columns else "latency"
    return pd.to_numeric(df[col], errors="coerce").dropna().to_numpy()


def draw(name, four_arrays, pair):
    data, colors, labels = [], [], []
    for label, single_dir, four_dir, log, is_ros2 in METHODS:
        path = receiver_log(four_dir if four_arrays else single_dir, log, pair)
        data.append(latencies(path))
        colors.append(ROS2 if is_ros2 else NON_ROS)
        labels.append(label)

    fig, ax = plt.subplots(figsize=(4.8, 2.3))
    positions = list(range(len(data), 0, -1))  # first method at the top
    bp = ax.boxplot(
        data, positions=positions, vert=False, widths=0.6, patch_artist=True,
        medianprops=dict(color=INK, linewidth=1.4),
        whiskerprops=dict(color=INK_2, linewidth=0.8),
        capprops=dict(color=INK_2, linewidth=0.8),
        flierprops=dict(marker="o", markersize=3, markerfacecolor="none",
                        markeredgewidth=0.7),
    )
    for box, flier, color in zip(bp["boxes"], bp["fliers"], colors):
        box.set(facecolor=color, edgecolor=color, alpha=0.85, linewidth=0.8)
        flier.set(markeredgecolor=color)

    ax.set_yticks(positions, labels)
    ax.set_xlim(*XLIM)
    ax.set_xticks(XTICKS)
    ax.set_xlabel("End-to-end latency (s)", color=INK_2)
    ax.grid(axis="x", color=GRID, linewidth=0.6)
    ax.set_axisbelow(True)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(INK_2)
    ax.tick_params(axis="y", length=0, colors=INK)
    ax.tick_params(axis="x", colors=INK_2)

    handles = [plt.Rectangle((0, 0), 1, 1, color=NON_ROS, alpha=0.85),
               plt.Rectangle((0, 0), 1, 1, color=ROS2, alpha=0.85)]
    ax.legend(handles, ["Non-ROS", "ROS 2"], loc="upper right", frameon=False,
              handlelength=1.0, handleheight=0.8, labelcolor=INK_2)

    fig.tight_layout()
    for ext in ("png", "pdf"):
        fig.savefig(os.path.join(OUT, f"{name}.{ext}"), dpi=300)
    plt.close(fig)
    print(f"{name}: " + ", ".join(f"{l}={d.mean():.3f}" for l, d in zip(labels, data)))


if __name__ == "__main__":
    plt.rcParams.update({"font.size": 9, "font.family": "DejaVu Sans"})
    os.makedirs(OUT, exist_ok=True)
    for name, four_arrays, pair in PANELS:
        draw(name, four_arrays, pair)
