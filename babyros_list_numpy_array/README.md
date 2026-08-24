# BabyROS Benchmark — List of Arrays

Benchmarks [BabyROS](https://docs.telekinesis.ai/babyros/introduction.html) (a Zenoh-based
pub/sub framework) carrying **four `float32` arrays totalling ~99 MB** in a single message,
matching the payload used by `uint8multiarray_list_numpy_array/` and
`string_list_numpy_array/`.

```python
SHAPES = [
    (1, 120, 160, 5, 64),
    (1, 120, 160, 5, 64, 3),
    (1, 120, 160, 6),
    (1, 120, 160)
]
```

See [`../babyros/README.md`](../babyros/README.md) for installation, the ARM/Jetson
constraints, and the congestion-control fix — all of which apply here identically.

---

## Why this payload shape matters

The ROS 2 methods pay a **packing tax** on this test. `UInt8MultiArray` must flatten four
arrays into one contiguous `uint8` buffer, which costs a constant ~1.2 s regardless of link
speed — enough that String (Base64) beats it on fast links despite sending 33% more bytes.

BabyROS has no equivalent step. Its NDDC wire format carries several arrays natively:
each array's raw bytes go into the payload back to back, and a JSON manifest records each
one's `{shape, dtype, offset, nbytes}`. No flattening, no per-element conversion, no
Base64 — the publisher hands numpy straight to the transport:

```python
pub.publish({"msg_id": msg_id, "publish_time": publish_time, **arrays})
```

---

## Running

Subscriber first. Run from inside this directory so `--folder` reproduces the results tree.

```bash
conda activate babyros
cd babyros_list_numpy_array

# receiver
python subscriber.py --folder ethernet/x86_machines

# sender
python publisher.py --folder ethernet/x86_machines
```

If the two machines do not discover each other by multicast, set endpoints explicitly:

```bash
python subscriber.py --folder ethernet/x86_machines --listen  tcp/0.0.0.0:7447
python publisher.py  --folder ethernet/x86_machines --connect tcp/<SUBSCRIBER-IP>:7447
```

Output is `publisher_log.csv` and `subscriber_log.csv` with the same columns as the ROS 2
list experiments (`msg_id, publish_time, receive_time, latency, type`).

---

## Results

Mean latency over ~100 messages.

| Configuration | UInt8MultiArray | String (Base64) | **BabyROS** | Winner |
| :--- | :--- | :--- | :--- | :--- |
| Ethernet, X86 → X86 | 3.2343 s | 2.0153 s | **1.1397 s** | BabyROS, 43% faster |
| Ethernet, X86 → Jetson | 4.1493 s | 3.3067 s | **1.1378 s** | BabyROS, 66% faster |
| WiFi, X86 → X86 | **8.3911 s** | 10.5983 s | 10.2884 s | UInt8MultiArray |

Jitter (standard deviation):

| Configuration | UInt8MultiArray | String (Base64) | **BabyROS** |
| :--- | :--- | :--- | :--- |
| Ethernet, X86 → X86 | 0.0222 s | 0.0276 s | **0.0094 s** |
| Ethernet, X86 → Jetson | 0.1084 s | 0.1231 s | **0.0121 s** |
| WiFi, X86 → X86 | **0.6709 s** | 1.3949 s | 1.2756 s |

**On Ethernet the packing tax decides it.** BabyROS transfers ~99 MB in 1.14 s on both
machine pairs — and again is unaffected by the Jetson (1.1378 s vs 1.1397 s), while every
ROS 2 method slows by 28–64% on ARM.

**On WiFi the ranking inverts.** This is the one configuration in the whole repo where
BabyROS does not win: `UInt8MultiArray` takes 8.39 s against BabyROS's 10.29 s. The packing
overhead that dominates on a fast link becomes irrelevant once the bottleneck is a ~140
Mbit/s radio, and DDS's fragmentation strategy handles the constrained link better here.
The measurement is stable, not an artefact — latency was flat across the run (+0.035 s
from the first ten messages to the last ten), so no queue backlog was inflating it.

---

## Plots

```bash
cd analysis && python3 plot_analysis_ethernet.py   # and plot_analysis.py for WiFi
```

Output lands in `analysis/ethernet/plots_babyros_2nd/` and
`analysis/wifi/plots_babyros_2nd/`, one folder per machine pair, each with a boxplot, CDF,
histogram and latency-vs-message-ID chart.

---

## Not yet collected

`wifi/diff_machines` (X86 → Jetson Nano over WiFi) has a `publisher_log.csv` but no
`subscriber_log.csv`, so that configuration is missing from the tables above. The
plotting script skips it automatically and still charts the two ROS 2 methods.
