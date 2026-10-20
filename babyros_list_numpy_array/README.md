# BabyROS Benchmark — List of Arrays

Benchmarks [BabyROS](https://docs.telekinesis.ai/babyros/introduction.html) (a Zenoh-based
pub/sub framework) carrying **four `float32` arrays totalling ~99 MB** in a single message,
matching the payload used by `uint8multiarray_list_numpy_array/` and
`string_list_numpy_array/`.

Part of the [Large-Data Communication Benchmark](../README.md) — see the main README for
the full comparison, and [`docs/methods.md`](../docs/methods.md) for the method index.

```python
SHAPES = [
    (1, 120, 160, 5, 64),
    (1, 120, 160, 5, 64, 3),
    (1, 120, 160, 6),
    (1, 120, 160)
]
```

See [`../babyros/README.md`](../babyros/README.md) for installation, the ARM/Jetson
constraints, the [message formats](../babyros/README.md#message-formats) and the
congestion-control fix — all of which apply here identically.

---

## Why this payload shape matters

The ROS 2 methods pay a **packing tax** on this test. `UInt8MultiArray` must flatten four
arrays into one contiguous `uint8` buffer, which costs a constant ~1.2 s regardless of link
speed — enough that String (Base64) beats it on fast links despite sending 33% more bytes.

BabyROS has no equivalent step. Its NDDC wire format carries several arrays natively:
each array's raw bytes go into the payload back to back, and a JSON manifest records each
one's `{shape, dtype, offset, nbytes}`. No flattening, no per-element conversion, no
Base64:

```python
pub.publish({"msg_id": msg_id, "publish_time": publish_time, **arrays})
```

It is not, however, a zero-copy handoff. zenoh-python's `ZBytes` accepts no buffer
protocol, so a numpy array cannot be given to the transport directly and the payload is
copied twice on the publisher — ~0.19 s at this size, which is essentially the whole gap
to Arrow IPC. See [the payload copy tax](../babyros/README.md#the-payload-copy-tax); it
applies to this payload shape identically.

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

All measured numbers are reported in the [main README's results table](../README.md#results).
Plots: [`analysis/`](../analysis/); per-experiment detail:
[README_ethernet.md](../README_ethernet.md).

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
`subscriber_log.csv`, so that configuration has no recorded result. The plotting script
skips it automatically and still charts the two ROS 2 methods.
