# Arrow Flight — one 150 MB array

Part of the [Large-Data Communication Benchmark](../README.md) — see the main README for
the full comparison, and [`docs/methods.md`](../docs/methods.md) for the method index.

| | |
| :--- | :--- |
| Transport | gRPC / HTTP2 (port 8815) |
| Serialization | Apache Arrow IPC (columnar), body outside protobuf |
| Payload | one 6125×6125 `float32` array (~150 MB) |
| Four-array variant | [`../arrow_flight_list_numpy_array/`](../arrow_flight_list_numpy_array/README.md) |

## How it works

**The technology.** [Arrow Flight](https://arrow.apache.org/docs/format/Flight.html) is a data-transfer framework built on **gRPC**: a service definition (`DoGet`, `DoPut`, `GetFlightInfo`, etc.) where a client can redeem a `Ticket` for a stream of `FlightData` messages. The important design decision is that **the Arrow record-batch data is not serialized field-by-field as protobuf data**. `FlightData` is a protobuf message, but its `data_body` field carries the Arrow IPC payload as raw bytes; Flight implementations use optimized serialization paths to avoid unnecessary protobuf parsing and memory copies. Flight therefore combines Arrow's efficient columnar representation with **gRPC's transport machinery**: HTTP/2 multiplexing, flow control, TLS and authentication mechanisms, concurrent streams, and a defined way to discover and parallelize data endpoints.


**What this benchmark sends.** The same payload as the Arrow IPC method — one
`large_binary` column holding `arr.tobytes()` — carried by a `FlightServerBase` returning a
`GeneratorStream` over `DoGet`. The batch itself differs in one respect: where
[`arrow_ipc/`](../arrow_ipc/README.md) puts `msg_id` and `publish_time` in two extra
*columns* of the same record batch, Flight carries them as a packed
`struct.pack('=Id', ...)` in its per-chunk **`app_metadata`** — a bytes slot that rides
alongside the data body — so the Flight schema has the data column and nothing else.

Data is generated **inside each client's own stream** rather than in a broadcast thread
feeding a queue. That is deliberate: it lets `publish_time` be stamped *before* Arrow
serialization. The earlier queue-based design left ~0.12 s of batch construction outside the
measurement while every other method here paid for its own serialization.

**What it costs.** Consistently ~6% behind raw Arrow IPC (**1.72 s / 1.15 s**, 74% of wire).
That 6% is HTTP/2 framing, per-stream flow-control windows and gRPC's stream bookkeeping —
work that buys real things this benchmark's single sender and single receiver never use.

## Running

`numpy` + `pyarrow` — `conda env create -f environment.yml`.

Start the **server first** on the sending machine, then the client on the receiving
machine; `--host` is the server's address and `--port` overrides the default (8815).
Run both sides from inside `arrow_flight/` and collect ~100 messages (5 s apart, ~9 minutes)
before stopping both with `Ctrl-C`.

```bash
cd arrow_flight
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
