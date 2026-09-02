# Arrow IPC + TCP — one 150 MB array

Part of the [Large-Data Communication Benchmark](../README.md) — see the main README for
the full comparison, and [`docs/methods.md`](../docs/methods.md) for the method index.

| | |
| :--- | :--- |
| Transport | raw TCP socket (port 9000) |
| Serialization | Apache Arrow IPC streaming format (columnar) |
| Payload | one 6125×6125 `float32` array (~150 MB) |
| Four-array variant | [`../arrow_ipc_list_numpy_array/`](../arrow_ipc_list_numpy_array/README.md) |

## How it works

**The technology.** [Apache Arrow](https://arrow.apache.org/) is a language-independent
*columnar in-memory* format. Its decisive property for this benchmark is that **the in-memory
layout is the wire layout**: column values live in flat, contiguous, aligned buffers, so
"serializing" means writing those buffers out as they already are, preceded by a small
FlatBuffers metadata block. There is no field-by-field encoding step, and on the receiving
side a buffer can be handed to `np.frombuffer` without a copy.

The **IPC streaming format** is how Arrow puts that on a byte stream: a schema message first,
then one encapsulated message per record batch (a continuation marker, the metadata length,
the FlatBuffers header, then the raw body buffers, 8-byte aligned). It is a framing format, not
a protocol — it assumes something else already delivers the bytes in order, which is precisely
what TCP does.

**What this benchmark sends.** A `RecordBatch` written straight into a plain TCP socket with
`pa.ipc.new_stream(sock.makefile('wb'), SCHEMA)`. The array rides in a `large_binary` column
(64-bit offsets, so a single value is not bounded by `binary`'s 2 GB ceiling); `msg_id` and
`publish_time` ride as two more columns in the same batch, so there is no side-channel and no
hand-packed header at all. The client opens the stream once with `pa.ipc.open_stream`, reads
batches in a loop, and rebuilds the array with `np.frombuffer`.

Two socket options do the tuning: a **256 MB send/receive buffer**
(`SO_SNDBUF`/`SO_RCVBUF`) so a 150 MB payload never stalls waiting for window space, and
**`TCP_NODELAY`** so nothing sits in Nagle's queue waiting for a full segment.

**What it costs.** It wins all four Ethernet tests — **1.61 s** on one big block, **1.09 s**
on four — reaching **93.5 MB/s against a 118 MB/s TCP ceiling (79% of the wire)**, and it
barely notices the Jetson (+4%). It wins because it does the least: one sender, one receiver,
one big message, and a framing format that already matches how numpy holds the data. Four
arrays cost it under 3%, because the schema simply gets **one column per array**
(`arr_0`…`arr_3`) — nothing is flattened, so there is no packing tax to pay.

## Running

`numpy` + `pyarrow` — `conda env create -f ../arrow_flight/environment.yml`.

Start the **server first** on the sending machine, then the client on the receiving
machine; `--host` is the server's address and `--port` overrides the default (9000).
Run both sides from inside `arrow_ipc/` and collect ~100 messages (5 s apart, ~9 minutes)
before stopping both with `Ctrl-C`.

```bash
cd arrow_ipc
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
