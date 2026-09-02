# ROS 2 String (Base64) — four arrays, ~99 MB

Part of the [Large-Data Communication Benchmark](../README.md) — see the main README for
the full comparison, and [`docs/methods.md`](../docs/methods.md) for the method index.

| | |
| :--- | :--- |
| Message type | `std_msgs/String` |
| Middleware | ROS 2 Jazzy / eProsima Fast DDS (`rmw_fastrtps_cpp`) |
| Payload | four `float32` arrays, 98.84 MB total (~132 MB on the wire) |
| Single-array variant | [`../string/`](../string/README.md) — full description of the message type and the DDS stack |

```python
SHAPES = [
    (1, 120, 160, 5, 64),
    (1, 120, 160, 5, 64, 3),
    (1, 120, 160, 6),
    (1, 120, 160)
]
```

## Why this payload shape matters

A `String` carries one character sequence, so the four arrays are joined behind a header of
four lengths and the whole buffer is Base64-encoded:

```python
header = struct.pack('=Id4I', msg_id, publish_time, *lengths)
binary_payload = header + b"".join(byte_arrays)
encoded_str = base64.b64encode(binary_payload).decode('utf-8')
```

It pays the same 33% expansion as on one big block — its loss is constant because its cause
is constant — but it assigns the encoded string directly rather than building a Python
`list[int]` the way `uint8multiarray_list_numpy_array/` does. That is why it **beats
UInt8MultiArray here** (2.0153 s vs 3.2343 s) while losing to it on one big block: a fixed
33% tax on a smaller payload is cheaper than the byte-array path's packing.

## Running

ROS 2 Jazzy + `numpy`. Both machines need the same `ROS_DOMAIN_ID`; start the **subscriber
first**, run both sides from inside `string_list_numpy_array/`, and collect ~100 messages (5 s apart,
~9 minutes) before stopping both with `Ctrl-C`.

```bash
source /opt/ros/jazzy/setup.bash
export ROS_DOMAIN_ID=0            # on both machines
cd string_list_numpy_array
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
