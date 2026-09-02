# Arrow IPC + TCP — four arrays, ~99 MB

Part of the [Large-Data Communication Benchmark](../README.md) — see the main README for
the full comparison, and [`docs/methods.md`](../docs/methods.md) for the method index.

| | |
| :--- | :--- |
| Transport | raw TCP socket (port 9000) |
| Serialization | Apache Arrow IPC streaming format (columnar) |
| Payload | four `float32` arrays, 98.84 MB total |
| Single-array variant | [`../arrow_ipc/`](../arrow_ipc/README.md) — full description of Arrow IPC and the socket tuning |

```python
SHAPES = [
    (1, 120, 160, 5, 64),
    (1, 120, 160, 5, 64, 3),
    (1, 120, 160, 6),
    (1, 120, 160)
]
```

## Why this payload shape matters

The schema simply gets **one `large_binary` column per array**, alongside the same two
metadata columns the single-array variant uses:

```python
SCHEMA = pa.schema(
    [pa.field(f'arr_{i}', pa.large_binary()) for i in range(len(SHAPES))]
    + [pa.field('msg_id', pa.uint32()), pa.field('publish_time', pa.float64())]
)
```

Nothing is flattened and nothing is copied together, so there is no packing tax to pay —
four arrays cost this method under 3% against its single-array result, where
`uint8multiarray_list_numpy_array/` loses more than half its throughput.

## Running

`numpy` + `pyarrow` — `conda env create -f ../arrow_flight/environment.yml`.

Start the **server first** on the sending machine, then the client on the receiving
machine; `--host` is the server's address and `--port` overrides the default (9000).
Run both sides from inside `arrow_ipc_list_numpy_array/` and collect ~100 messages (5 s apart, ~9 minutes)
before stopping both with `Ctrl-C`.

```bash
cd arrow_ipc_list_numpy_array
```

**X86 → X86**

```bash
python3 server.py --folder ethernet/x86_machines                     # sending X86
python3 client.py --folder ethernet/x86_machines --host <server-ip>  # receiving X86
```

**X86 → Jetson Nano**

```bash
python3 server.py --folder ethernet/diff_machines                    # sending X86
python3 client.py --folder ethernet/diff_machines --host <server-ip> # Jetson Nano
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
