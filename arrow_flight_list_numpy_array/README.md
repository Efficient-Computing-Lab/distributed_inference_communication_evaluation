# Arrow Flight — four arrays, ~99 MB

Part of the [Large-Data Communication Benchmark](../README.md) — see the main README for
the full comparison, and [`docs/methods.md`](../docs/methods.md) for the method index.

| | |
| :--- | :--- |
| Transport | gRPC / HTTP2 (port 8815) |
| Serialization | Apache Arrow IPC (columnar), body outside protobuf |
| Payload | four `float32` arrays, 98.84 MB total |
| Single-array variant | [`../arrow_flight/`](../arrow_flight/README.md) — full description of Flight, `DoGet` and `app_metadata` |

```python
SHAPES = [
    (1, 120, 160, 5, 64),
    (1, 120, 160, 5, 64, 3),
    (1, 120, 160, 6),
    (1, 120, 160)
]
```

## Why this payload shape matters

The batch carries **one `large_binary` column per array** — the same mapping
[`arrow_ipc_list_numpy_array/`](../arrow_ipc_list_numpy_array/README.md) uses:

```python
SCHEMA = pa.schema([pa.field(f'arr_{i}', pa.large_binary()) for i in range(len(SHAPES))])
```

The difference from the IPC variant is where the metadata goes: the IPC schema appends
`msg_id` and `publish_time` as two further columns, while here they stay in Flight's
per-chunk `app_metadata`, so the schema is exactly the four array columns. Either way
nothing is glued, so changing payload shape costs this method almost nothing.

## Running

`numpy` + `pyarrow` — `conda env create -f ../arrow_flight/environment.yml`.

Start the **server first** on the sending machine, then the client on the receiving
machine; `--host` is the server's address and `--port` overrides the default (8815).
Run both sides from inside `arrow_flight_list_numpy_array/` and collect ~100 messages (5 s apart, ~9 minutes)
before stopping both with `Ctrl-C`.

```bash
cd arrow_flight_list_numpy_array
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
