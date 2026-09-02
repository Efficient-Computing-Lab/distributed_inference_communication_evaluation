# gRPC (repeated bytes) — four arrays, ~99 MB

Part of the [Large-Data Communication Benchmark](../README.md) — see the main README for
the full comparison, and [`docs/methods.md`](../docs/methods.md) for the method index.

| | |
| :--- | :--- |
| Transport | gRPC / HTTP2 (port 50051) |
| Serialization | Protobuf `repeated bytes payloads` |
| Payload | four `float32` arrays, 98.84 MB total |
| Single-array variant | [`../grpc_string/`](../grpc_string/README.md) — full description of gRPC, HTTP/2 and protobuf |

```python
SHAPES = [
    (1, 120, 160, 5, 64),
    (1, 120, 160, 5, 64, 3),
    (1, 120, 160, 6),
    (1, 120, 160)
]
```

`string_comm_list_pb2.py` and `string_comm_list_pb2_grpc.py` are pre-generated and committed.

## Why this payload shape matters

The message uses **`repeated bytes payloads`** — the idiomatic protobuf mapping, and the fair
counterpart to Arrow's one-column-per-array:

```python
payloads=[a.tobytes() for a in arrays]
```

Like Arrow, it never glues. Its throughput is essentially unchanged between the two payload
shapes (69.2 → 69.3 MB/s), confirming that its loss against Arrow is per-byte — the
serialize/parse copies — not per-message.

## Running

`numpy` + `grpcio` — `conda env create -f ../grpc_string/environment.yml`.

Start the **server first** on the sending machine, then the client on the receiving
machine; `--host` is the server's address and `--port` overrides the default (50051).
Run both sides from inside `grpc_string_list_numpy_array/` and collect ~100 messages (5 s apart, ~9 minutes)
before stopping both with `Ctrl-C`.

```bash
cd grpc_string_list_numpy_array
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

Both ends raise `grpc.max_{send,receive}_message_length` to 512 MB for this variant.

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
