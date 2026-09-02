# gRPC (protobuf bytes) — one 150 MB array

Part of the [Large-Data Communication Benchmark](../README.md) — see the main README for
the full comparison, and [`docs/methods.md`](../docs/methods.md) for the method index.

| | |
| :--- | :--- |
| Transport | gRPC / HTTP2 (port 50051) |
| Serialization | Protobuf `bytes` field — binary, not Base64 |
| Payload | one 6125×6125 `float32` array (~150 MB) |
| Four-array variant | [`../grpc_string_list_numpy_array/`](../grpc_string_list_numpy_array/README.md) |

`string_comm_pb2.py` and `string_comm_pb2_grpc.py` are pre-generated and committed — no
`protoc` step is needed to run this benchmark.

## How it works

**The technology.** [gRPC](https://grpc.io/) is Google's RPC framework: services declared in
`.proto` files, code generated for both ends, messages carried over **HTTP/2**. HTTP/2 gives
it multiplexed streams over one TCP connection, binary framing, and per-stream flow control —
so a 150 MB message is chopped into DATA frames and paced by window updates. **Protocol
Buffers** is the serialization: a compact tag-length-value binary encoding where each field
gets a varint tag, and a `bytes` field is written as tag + length + payload.

Unlike Arrow, protobuf's wire format is *not* the in-memory format. The payload is **copied
into** the protobuf message when it is serialized and **copied out** when it is parsed — and
in Python, materializing the `bytes` field costs another copy. At 150 MB per message, those
copies are the whole story.

**What this benchmark sends.** A server-streaming RPC —
`rpc Stream(StreamRequest) returns (stream DataMessage)` — whose message carries `msg_id`,
`publish_time`, a `bytes payload`, and a type label. gRPC's default 4 MB message limit is far
too small here, so both ends raise `grpc.max_{send,receive}_message_length` to **200 MB**
(512 MB for the list variant). Nothing is base64-encoded: `bytes` is binary on the wire.

For four arrays it uses **`repeated bytes payloads`** — the idiomatic protobuf mapping, and the
fair counterpart to Arrow's one-column-per-array. Like Arrow, it never glues.

**What it costs.** ~69 MB/s, **59% of wire** (**2.17 s / 1.43 s**), behind both Arrow methods
despite sending exactly the same bytes over a comparable transport. The gap is the
serialize/parse copies — which is the cleanest available measurement of what Arrow's
"the layout is the format" claim is actually worth: about 24 MB/s here. Changing payload shape
costs it nothing (69.2 → 69.3 MB/s), confirming the loss is per-byte, not per-message.

## Running

`numpy` + `grpcio` — `conda env create -f environment.yml`.

Start the **server first** on the sending machine, then the client on the receiving
machine; `--host` is the server's address and `--port` overrides the default (50051).
Run both sides from inside `grpc_string/` and collect ~100 messages (5 s apart, ~9 minutes)
before stopping both with `Ctrl-C`.

```bash
cd grpc_string
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

Both ends raise `grpc.max_{send,receive}_message_length` to 200 MB; gRPC's 4 MB default is
far too small for this payload.

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
