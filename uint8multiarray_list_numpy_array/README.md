# ROS 2 UInt8MultiArray — four arrays, ~99 MB

Part of the [Large-Data Communication Benchmark](../README.md) — see the main README for
the full comparison, and [`docs/methods.md`](../docs/methods.md) for the method index.

| | |
| :--- | :--- |
| Message type | `std_msgs/UInt8MultiArray` |
| Middleware | ROS 2 Jazzy / eProsima Fast DDS (`rmw_fastrtps_cpp`) |
| Payload | four `float32` arrays, 98.84 MB total |
| Single-array variant | [`../uint8multiarray/`](../uint8multiarray/README.md) — full description of the message type and the DDS stack |

```python
SHAPES = [
    (1, 120, 160, 5, 64),
    (1, 120, 160, 5, 64, 3),
    (1, 120, 160, 6),
    (1, 120, 160)
]
```

## Why this payload shape matters

A `uint8[]` field is one contiguous sequence, so four separate arrays must first be joined
into a single buffer behind a header carrying the four lengths:

```python
header = struct.pack('=Id4I', msg_id, publish_time, *lengths)
binary_payload = header + b"".join(byte_arrays)
msg.data = list(binary_payload)        # bytes → list[int] for UInt8MultiArray
```

That joining — and, in this script, the `list()` conversion — is pure CPU that scales with
payload size and does not shrink on a faster network. It is why this method takes **1.13 s
longer to send 34% less data** than the single-array variant, and why it drops to **26% of
wire speed**, last of the six methods. The non-ROS methods carry several arrays side by side
and never pay it.

## Running

ROS 2 Jazzy + `numpy`. Both machines need the same `ROS_DOMAIN_ID`; start the **subscriber
first**, run both sides from inside `uint8multiarray_list_numpy_array/`, and collect ~100 messages (5 s apart,
~9 minutes) before stopping both with `Ctrl-C`.

```bash
source /opt/ros/jazzy/setup.bash
export ROS_DOMAIN_ID=0            # on both machines
cd uint8multiarray_list_numpy_array
```

**X86 → X86**

```bash
python3 subscriber.py --folder ethernet/x86_machines   # receiving X86
python3 publisher.py  --folder ethernet/x86_machines   # sending X86
```

**X86 → Jetson Nano**

```bash
python3 subscriber.py --folder ethernet/diff_machines  # Jetson Nano
python3 publisher.py  --folder ethernet/diff_machines  # sending X86
```

### Folder naming

`--folder` encodes the machine pair: `ethernet/x86_machines` for X86 → X86 and
`ethernet/diff_machines` for X86 → Jetson Nano. Use these exact names to extend the existing
results — every method uses the same two.

## Results

All measured numbers for this configuration are reported in the
[main README's results table](../README.md#results). Plots: [`analysis/`](../analysis/);
per-experiment detail: [README_ethernet.md](../README_ethernet.md).

## Verifying a run

Sent and received counts should match — a gap means messages were dropped and the latency
figures are survivorship-biased:

```bash
wc -l ethernet/x86_machines/publisher_log.csv ethernet/x86_machines/subscriber_log.csv
```
