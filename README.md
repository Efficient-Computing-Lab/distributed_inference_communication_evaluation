# ROS 2 & Non-ROS Communication Latency Benchmark

**The question:** if a robot has to send a big block of numbers to another machine, which
way of sending it is fastest?

We send the same data — about **150 MB of numbers** — over and over between two computers,
and time how long each message takes to arrive. We try six different ways of sending it,
over both a network cable and WiFi, and to two kinds of receiver: a normal PC and a small
Jetson Nano board.

Every method sends exactly the same numbers, so any difference in time comes from the
sending method, not the data.

---

## Hardware Setup

| Machine | Role | CPU |
| :--- | :--- | :--- |
| X86 Machine A | Publisher / Server | x86-64 |
| X86 Machine B | Subscriber / Client | x86-64 |
| Jetson Nano | Subscriber / Client | ARM Cortex-A57 |

Network configuration for WiFi experiments: the X86 publisher is connected via **WiFi**; X86 Machine B and the Jetson Nano are connected via **Ethernet**.

Network configuration for Ethernet-only experiments: all machines communicate via **Ethernet**.

---

## Network Baseline (iperf3)

Raw network throughput was characterized using **iperf3** before any ROS 2 middleware overhead — establishing the available bandwidth ceiling for the two link types used in all experiments.

Each dataset consists of repeated 30-second iperf3 runs between the same client/server pair used in the ROS 2 benchmarks:

| Dataset | Source zip | Protocol | Valid runs |
| :--- | :--- | :--- | :--- |
| Ethernet UDP | `iperf_outputs.zip` | UDP | 100 |
| Ethernet TCP | `iperf_tcp_outputs.zip` | TCP | 100 |
| WiFi UDP | `wifi_iperf_outputs.zip` | UDP | 98 |
| WiFi TCP | `wifi_iperf_outputs.zip` | TCP | 96 |

### Ethernet

> All machines connected to a Gigabit switch. Client IP `147.102.19.162` → Server IP `147.102.19.67`.

| Protocol | Throughput sent (mean ± stdev) | Throughput recv (mean ± stdev) | RTT (mean) | Jitter (mean) | Packet loss | TCP retransmits |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **UDP** | 956.18 ± 0.25 Mbit/s | 956.15 ± 0.25 Mbit/s | — | 0.016 ms | 0.0004% | — |
| **TCP** | 942.01 ± 0.20 Mbit/s | 941.35 ± 0.12 Mbit/s | 1.96 ms | — | — | 0 (zero) |

The Ethernet link saturates at ~956 Mbit/s (UDP) / ~942 Mbit/s (TCP) with essentially no jitter, zero packet loss, and zero TCP retransmits across all 100 runs — a near-ideal Gigabit channel.

### WiFi

> Publisher machine on WiFi (`147.102.19.185`), server on Ethernet (`147.102.19.67`). This matches the WiFi experiment topology used in the ROS 2 benchmarks.

| Protocol | Throughput sent (mean ± stdev) | Throughput recv (mean ± stdev) | RTT (mean) | Jitter (mean) | Packet loss (mean / max) | TCP retransmits (mean / max) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **UDP** | 138.75 ± 11.98 Mbit/s | 138.62 ± 11.90 Mbit/s | — | 0.11 ms | 0.065% / 0.48% | — |
| **TCP** | 142.51 ± 13.62 Mbit/s | 141.68 ± 13.64 Mbit/s | 29.43 ms | — | — | 4.9 avg / 85 max |

The WiFi link delivers ~140 Mbit/s on average but with high variability (stdev ~12–14 Mbit/s, min ~109 Mbit/s, max ~197 Mbit/s), a 15× higher RTT (29 ms vs 2 ms on Ethernet), and intermittent TCP retransmits (avg 4.9, max 85 per 30-second run).

### Ethernet vs WiFi comparison

| Metric | Ethernet | WiFi | Ratio |
| :--- | :--- | :--- | :--- |
| TCP throughput (mean) | 942 Mbit/s | 143 Mbit/s | **~6.6×** |
| UDP throughput (mean) | 956 Mbit/s | 139 Mbit/s | **~6.9×** |
| Throughput variability (stdev) | 0.2 Mbit/s | 12–14 Mbit/s | **~60–70×** |
| RTT (mean) | 1.96 ms | 29.4 ms | **~15×** |
| Jitter | 0.016 ms | 0.11 ms | **~7×** |
| Packet loss | 0.0004% | 0.065% | **~163×** |

The ~6.7× raw bandwidth gap between Ethernet and WiFi directly explains the ~4–6× increase in ROS 2 transfer latency observed in the benchmark results. The additional gap between raw bandwidth ratios and ROS 2 latency ratios is attributable to DDS fragmentation and discovery overhead — which scales poorly on lossy, high-RTT links.

---

## Methods Compared

Six methods are benchmarked head-to-head. They all send the same numbers and all measure the
same interval — **the clock starts before the array is created and stops when the receiver
holds it again** — so every figure includes the method's own packing cost, not just its time
on the wire.

Each method is tested with two shapes of data, because they behave differently:

- **One big block** — a single 6125×6125 grid of numbers (150 MB). Like one large image.
- **Four smaller blocks** — four grids of different sizes, 99 MB in total. Like the several
  outputs a neural network produces at once.

The second shape matters because some methods can send several blocks side by side, while
others must first glue them into one long strip — and that gluing costs time.

### ROS 2 (DDS / FastDDS middleware)

| Method | Serialization | Transmission size | Directory |
| :--- | :--- | :--- | :--- |
| **UInt8MultiArray** | Raw binary (`.tobytes()` / `np.frombuffer()`) | ~150 MB | `uint8multiarray/`, `uint8multiarray_list_numpy_array/` |
| **String (Base64)** | Base64 text encoding | ~200 MB (+33%) | `string/`, `string_list_numpy_array/` |

**The technology.** ROS 2 does not implement networking itself. It defines an abstract
middleware interface (RMW) and delegates everything to **DDS** — the OMG's Data Distribution
Service, a data-centric publish/subscribe standard from the avionics and defence world. ROS 2
Jazzy's default implementation is **eProsima Fast DDS** (`rmw_fastrtps_cpp`), which is what
every ROS 2 number in this repo was measured on.

Four properties of that stack explain the results:

- **RTPS over UDP.** DDS speaks the Real-Time Publish-Subscribe wire protocol, by default over
  UDP — unicast and multicast. UDP has no built-in reliability, so DDS builds its own on top:
  readers send NACKs for missing pieces and writers retransmit.
- **Fragmentation.** A UDP datagram cannot carry 150 MB, so RTPS splits every large sample
  into thousands of `DATA_FRAG` submessages sized to the link's MTU, and the reader
  reassembles them. Every fragment is bookkeeping: sequence numbers, heartbeats, ACKNACKs.
  This is why ROS 2's disadvantage grows on lossy, high-RTT links like WiFi, where a single
  lost fragment stalls the whole sample.
- **CDR serialization.** Messages are described in IDL and serialized to Common Data
  Representation. For a `uint8[]` field that is close to a straight memory copy, but it is
  still a copy — into the DDS writer's buffer on the way out, and out of the reader's cache on
  the way in.
- **Discovery and QoS.** Participants announce themselves by multicast (SPDP), then exchange
  endpoint descriptions (SEDP), then match on QoS policies. This is what gives ROS 2 its
  best feature — a publisher that broadcasts to anyone who happens to be listening, with no
  addresses configured — and it is genuine work the point-to-point methods below never do.

Neither ROS 2 message type understands numpy, so both methods flatten the array to bytes and
prepend a 12-byte header (`struct.pack('=Id', msg_id, publish_time)`) carrying the message
identity and send timestamp. Both publish on `big_topic` with queue depth 10.

#### UInt8MultiArray — raw bytes down a byte-array message

`std_msgs/UInt8MultiArray` is a `uint8[]` payload plus a `MultiArrayLayout` describing
dimensions. Only the byte array is used here: `msg.data = header + arr.tobytes()`, nothing
encoded, nothing added. This is the honest ROS 2 way to move binary data, and on one big
block it is the faster of the two ROS 2 options (**2.11 s** X86→X86) because the bytes on the
wire are exactly the bytes in memory.

Two things cost it dearly:

- **The receiver does real work.** DDS reassembly and CDR deserialization of a 150 MB sample
  is CPU-bound, and CPU is exactly what a Jetson Nano does not have: **3.59 s to the Jetson
  versus 2.11 s to an X86, +70%**. No non-ROS method in this repo shows more than 4%. This is
  the single clearest finding in the study — ROS 2's cost lands on the receiver, and the
  weaker the receiver, the worse it lands.
- **It carries only one strip of bytes.** A `uint8[]` field is one contiguous sequence, so
  four separate arrays must first be joined into a single buffer (`b"".join(byte_arrays)`
  behind a 4-length header). That is pure CPU that scales with payload size, and it is why the
  method takes **1.13 s longer to send 34% less data** (3.23 s on four blocks) and falls to
  26% of wire speed — last of six.


#### String (Base64) — bytes as text

The same binary payload, base64-encoded into a `std_msgs/String`. Base64 is a 6-bit alphabet:
it rewrites every 3 bytes as 4 printable ASCII characters, so the payload grows by exactly
one third — **150 MB becomes 200 MB on the wire** — and both ends pay CPU for the transform
(`b64encode` on the sender, `b64decode` on the receiver). On top of that, a DDS `string` field
is a length-prefixed, null-terminated character sequence, so the middleware treats 200 MB of
payload as text rather than as an opaque buffer.

This is what people reach for when a `String` topic is the only thing available, and it is the
most expensive option here for a reason that never goes away. It sits at **~43% of wire speed
on both payload shapes** — its loss is constant because its cause is constant. It finishes
last on one big block (**2.98 s** X86→X86, **5.08 s** to the Jetson, the worst number in the
study), yet **beats UInt8MultiArray on four blocks** (2.02 s vs 3.23 s): a fixed 33% tax on a
smaller payload is cheaper than the joining — and, in that script, the `list()` conversion —
the byte-array path pays.

> `string/` and `uint8multiarray/` ship a `custom_fast_dds.xml` (async publish, 2 GB socket
> buffers) for pushing 150 MB over UDP, but it is not applied automatically and no recorded
> result uses it. All ROS 2 numbers here are stock Fast DDS defaults.

### Non-ROS (Ethernet only)

| Method | Transport | Serialization | Directory |
| :--- | :--- | :--- | :--- |
| **Arrow IPC + TCP** | Raw TCP socket | Apache Arrow IPC (columnar) | `arrow_ipc/`, `arrow_ipc_list_numpy_array/` |
| **Arrow Flight (gRPC)** | gRPC / HTTP2 | Apache Arrow IPC (columnar) | `arrow_flight/`, `arrow_flight_list_numpy_array/` |
| **gRPC String (bytes)** | gRPC / HTTP2 | Protobuf `bytes` field | `grpc_string/`, `grpc_string_list_numpy_array/` |
| **BabyROS** | Zenoh | Raw numpy bytes + JSON manifest (NDAR/NDDC) | `babyros/`, `babyros_list_numpy_array/` |

Three of the four are **server-first and point-to-point**: the receiver connects to a stream
and the sender pushes a message every 5 s. That is a weaker guarantee than ROS 2 topics —
nobody discovers anybody, and there is one receiver — but it also removes discovery and
per-sample negotiation from the measured path. BabyROS is the exception: it keeps broadcast
pub/sub.

#### Arrow IPC + TCP — the benchmark winner

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

#### Arrow Flight — the same payload with a managed connection

**The technology.** [Arrow Flight](https://arrow.apache.org/docs/format/Flight.html) is a
data-transfer framework built on **gRPC**: a service definition (`DoGet`, `DoPut`,
`GetFlightInfo`, …) where a client redeems a `Ticket` for a stream of `FlightData` messages.
The important design decision is that **the Arrow record batch body never goes through
protobuf**. Flight installs a custom gRPC serializer that writes the Arrow buffers directly
into the gRPC frame, so the payload is not re-encoded field by field the way an ordinary
protobuf message would be. Flight therefore gives you Arrow's zero-copy body *plus* gRPC's
connection management: HTTP/2 multiplexing, flow control, TLS and auth hooks, several
concurrent clients, and a defined way to discover and parallelize streams.

**What this benchmark sends.** Identical Arrow batches to the Arrow IPC method, carried by a
`FlightServerBase` returning a `GeneratorStream` over `DoGet`. `msg_id` and `publish_time`
travel in Flight's per-chunk `app_metadata` field — a bytes slot that rides alongside the data
body — rather than as extra columns.

Data is generated **inside each client's own stream** rather than in a broadcast thread
feeding a queue. That is deliberate: it lets `publish_time` be stamped *before* Arrow
serialization. The earlier queue-based design left ~0.12 s of batch construction outside the
measurement while every other method here paid for its own serialization.

**What it costs.** Consistently ~6% behind raw Arrow IPC (**1.72 s / 1.15 s**, 74% of wire).
That 6% is HTTP/2 framing, per-stream flow-control windows and gRPC's stream bookkeeping —
work that buys real things this benchmark's single sender and single receiver never use.

#### gRPC String (bytes) — protobuf, no Arrow

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

#### BabyROS (Zenoh) — ROS-style pub/sub without DDS

**The technology.** [Zenoh](https://zenoh.io/) is an Eclipse Foundation protocol from
ZettaScale that unifies pub/sub, query and storage under one abstraction. Where DDS matches
*topics* between typed endpoints, Zenoh routes on **key expressions** (`big_topic`, with
wildcards) and treats payloads as opaque bytes — no IDL, no type registry, no CDR. Nodes can
run as peers (direct, mesh) or through routers; peers on a subnet find each other by
**multicast scouting**, and explicit `listen`/`connect` endpoints work when multicast does
not. The transport layer runs over TCP, UDP, QUIC, Unix sockets or shared memory, batches
small messages, and — critically for this benchmark — exposes **per-publisher congestion
control**. Zenoh is not exotic in a ROS context: `rmw_zenoh` is now an official ROS 2
middleware, so this is roughly "ROS 2 with the DDS layer swapped out".

[BabyROS](https://docs.telekinesis.ai/babyros/introduction.html) (Telekinesis, Apache 2.0) is
a small pure-Python framework on top of it that keeps the ROS shape —
`Publisher(topic=...)`, `Subscriber(topic=..., callback=...)`, `history`/`depth` QoS — while
carrying numpy arrays natively. `pub.publish({"msg_id": ..., "publish_time": ..., "data":
arr})` sends the array bytes raw with an **Arrow-style JSON manifest (NDAR/NDDC)** describing
dtype and shape. No header packing, no base64, and `compression=None` keeps the 150 MB
uncompressed on the wire — the same deal Arrow gets, reached from the other direction.

**What it costs.** ~11% over raw Arrow IPC (**1.79 s / 1.27 s**, 71% of wire) — and that 11%
buys back the one thing every other non-ROS method here gives up: **broadcast pub/sub**, a
sender publishing to any number of automatically-discovered receivers. Like the other non-ROS
methods it is nearly immune to the receiver's CPU (**+1% on the Jetson**, against ROS 2's
+70%), and it is by far the **steadiest**: 0.49 s standard deviation on WiFi→Jetson where
UInt8MultiArray shows 4.34 s — roughly 9× tighter on a mean that is already 3× lower.

**Two settings stock BabyROS does not apply** were required to get there, both documented in
[babyros/README.md](babyros/README.md):

- **`CongestionControl.BLOCK`.** BabyROS declares its Zenoh publisher with no congestion
  setting, so Zenoh's default `DROP` applies: a 150 MB payload overflows the transmit queue
  and is **silently discarded** while `put()` returns cleanly and the publisher logs success.
  Delivery was ~20% same-machine and ~0% cross-machine until the publisher re-declared with
  `BLOCK`, which waits for queue space instead. It is 100% now; `--allow-drop` reproduces the
  original behaviour.
- **`wait_before_close = 60 s`.** How long a blocking publisher may wait for queue space
  before Zenoh tears down the transport session. The stock default is below the ~9 s a 150 MB
  payload needs over WiFi, so the session died mid-run. `rmw_zenoh` raises the same value for
  the same reason.

> `tcp_raw/`, `nfs/` and `babyros_client_server/` also ship in this repo but have no recorded
> results and appear in no ranking — see [Running the Benchmarks](#running-the-benchmarks).

---

## Running the Benchmarks

Every method follows the same shape: **start the receiver first, then the sender.** Each
side writes its own CSV into `--folder`, and latency is computed on the receiver.

All commands below are run **from inside the method's directory**, so `--folder` reproduces
the results tree (e.g. running `string/publisher.py` with `--folder wifi/x86_machines`
creates `string/wifi/x86_machines/`).

Let each run collect ~100 messages (5 s apart → ~9 minutes), then stop both sides with
`Ctrl-C`.

### Folder naming

`--folder` encodes network and machine pair. The naming is **not** uniform across the repo —
match these exactly to extend existing results:

| Machine pair | Single-array methods | List-of-arrays & non-ROS methods |
| :--- | :--- | :--- |
| Publisher + subscriber on one X86 | `wifi/same_machine` | `wifi/same_machine` |
| X86 → X86 | `wifi/x86_machines`, `ethernet/x86_machines` | same |
| X86 → Jetson Nano | `wifi/diff_machine` ⚠️ *singular* | `wifi/diff_machines`, `ethernet/diff_machines` |

### Environment

| Method | Requirements |
| :--- | :--- |
| ROS2 (`string`, `uint8multiarray`, `*_list_numpy_array`) | ROS 2 Jazzy + `numpy` — `source /opt/ros/jazzy/setup.bash` |
| `arrow_flight`, `arrow_ipc` | `conda env create -f arrow_flight/environment.yml` (numpy + pyarrow) |
| `grpc_string` | `conda env create -f grpc_string/environment.yml` (`string_comm_pb2*.py` are pre-generated) |
| `tcp_raw`, `nfs` | numpy only |
| `babyros` | Python 3.11–3.12 venv — see [babyros/README.md](babyros/README.md) |
| `analysis/` | `pip install -r analysis/requirements.txt` |

### ROS 2 methods

Both sides must share a `ROS_DOMAIN_ID`. Run the subscriber first:

```bash
cd uint8multiarray            # or: string, string_list_numpy_array,
                              #     uint8multiarray_list_numpy_array
export ROS_DOMAIN_ID=0

python3 subscriber.py --folder ethernet/x86_machines   # receiver machine
python3 publisher.py  --folder ethernet/x86_machines   # sender machine
```

`string/` and `uint8multiarray/` ship a `custom_fast_dds.xml` tuning profile (async publish,
2 GB socket buffers) for pushing 150 MB over UDP. It is **not** applied automatically and no
recorded result documents its use; to enable it, export the path before launching **both**
sides:

```bash
export FASTRTPS_DEFAULT_PROFILES_FILE=$PWD/custom_fast_dds.xml
```

### Non-ROS methods

Server first, then client. Replace `<server-ip>` with the sender's address:

```bash
# Arrow Flight (gRPC, port 8815)
cd arrow_flight
python3 server.py --folder ethernet/x86_machines
python3 client.py --folder ethernet/x86_machines --host <server-ip>

# Arrow IPC + TCP (port 9000)
cd arrow_ipc
python3 server.py --folder ethernet/x86_machines
python3 client.py --folder ethernet/x86_machines --host <server-ip>

# gRPC String (port 50051)
cd grpc_string
python3 server.py --folder ethernet/x86_machines
python3 client.py --folder ethernet/x86_machines --host <server-ip>

# BabyROS (Zenoh, auto-discovers peers on the same subnet)
cd babyros
python3 subscriber.py --folder ethernet/x86_machines
python3 publisher.py  --folder ethernet/x86_machines
```

`arrow_ipc`, `arrow_flight`, `grpc_string` and `tcp_raw` all accept `--port` if the default
is taken. `tcp_raw/` follows the same server/client pattern on port 9000.

### NFS (out-of-band transfer)

Sends only a notification over ROS 2; the array travels over the NFS mount. Both paths must
point at the same share:

```bash
cd nfs
python3 subscriber.py --folder ethernet/x86_machines --nfs-path /var/locally-mounted
python3 publisher.py  --folder ethernet/x86_machines --nfs-path /mnt/myshareddir
```

### Network baseline (iperf3)

Run on the machine that will host the publisher. Requires `iperf3` on both hosts and SSH
access to the remote:

```bash
python3 udp_test.py --ip <remote-ip> --remote_user <remote-user> --trials 100 --duration 30
python3 tcp_test.py --ip <remote-ip> --remote_user <remote-user> --trials 100 --duration 30
```

Each writes a timestamped folder with per-run JSON, both machines' specs, and `summary.json`.

### Generating plots

Run from inside `analysis/` — output paths are relative to the working directory:

```bash
cd analysis
python3 plot_analysis.py            # WiFi  → wifi/plots/, wifi/plots_2nd/
python3 plot_analysis_ethernet.py   # Ethernet → ethernet/plots{,_2nd,_non_ros}/
```

Both scripts read the subscriber CSVs directly and will fail if a configuration has not been
collected yet.

### Verifying a run

Sent and received counts should match. A gap means messages were dropped and the latency
figures are survivorship-biased:

```bash
wc -l <method>/<network>/<pair>/publisher_log.csv <method>/<network>/<pair>/subscriber_log.csv
```

---

## Experiment Matrix

| Configuration | Network | Detailed Results |
| :--- | :--- | :--- |
| Same machine (X86) | — | [README_wifi.md](README_wifi.md) |
| X86 publisher → X86 subscriber | WiFi | [README_wifi.md](README_wifi.md) |
| X86 publisher → Jetson Nano subscriber | WiFi | [README_wifi.md](README_wifi.md) |
| X86 publisher → X86 subscriber | Ethernet | [README_ethernet.md](README_ethernet.md) |
| X86 publisher → Jetson Nano subscriber | Ethernet | [README_ethernet.md](README_ethernet.md) |

---

## Results Summary

### One big block — 150 MB, over the cable

Every number below is measured the same way: the clock starts before the test data is made
and stops when the receiver has it. 100 messages per method.

| Method | X86 → X86 | X86 → Jetson | Speed | Slowdown on the Jetson |
| :--- | ---: | ---: | ---: | ---: |
| **Arrow IPC + TCP** | **1.6057s** | **1.6648s** | **93.5 MB/s** | +4% |
| Arrow Flight (gRPC) | 1.7163s | 1.7235s | 87.4 MB/s | +0% |
| BabyROS (Zenoh) | 1.7858s | 1.7985s | 84.0 MB/s | +1% |
| ROS2 UInt8MultiArray | 2.1086s | 3.5886s | 71.2 MB/s | **+70%** |
| gRPC String (bytes) | 2.1671s | 2.2333s | 69.2 MB/s | +3% |
| ROS2 String (Base64) | 2.9777s | 5.0823s | 50.4 MB/s | **+71%** |

**Winner: Arrow IPC + TCP.** A plain network socket carrying the numbers as-is. It moves
93.5 MB/s where the cable itself tops out at 118 MB/s, so it uses **79%** of what the wire
can carry.

**The receiving computer matters enormously — but only for ROS 2.** Send to a small Jetson
Nano board instead of a full PC and the two ROS 2 methods take about **70% longer**. Every
other method changes by 4% or less. ROS 2 makes the receiver do a lot of unpacking work, and
the small board cannot keep up; the others ask far less of it.

**Turning numbers into text is the worst idea here.** String (Base64) writes the data as text,
making it 33% bigger, and finishes last of six — 5.08s to the Jetson, three times slower than
the winner.

### Four smaller blocks — 98.84 MB, over the cable

The same four arrays a neural network might produce at once, sent in one message.

| Method | X86 → X86 | X86 → Jetson | Speed | Slowdown on the Jetson |
| :--- | ---: | ---: | ---: | ---: |
| **Arrow IPC + TCP** | **1.0866s** | **1.1063s** | **91.0 MB/s** | +2% |
| Arrow Flight (gRPC) | 1.1544s | 1.1667s | 85.6 MB/s | +1% |
| BabyROS (Zenoh) | 1.2686s | 1.2653s | 77.9 MB/s | −0% |
| gRPC (repeated bytes) | 1.4255s | 1.4787s | 69.3 MB/s | +4% |
| ROS2 String (Base64) | 2.0153s | 3.3067s | 49.0 MB/s | **+64%** |
| ROS2 UInt8MultiArray | 3.2343s | 4.1493s | 30.6 MB/s | +28% |

**Winner: Arrow IPC + TCP again**, in both machine pairings.

---

## What changes between one block and four?

This is the most interesting result in the study, because **the two ROS 2 methods swap
places** while nothing else moves.

| | One block (150 MB) | Four blocks (98.84 MB) |
| :--- | :--- | :--- |
| UInt8MultiArray | **2.1086s** — beats String | **3.2343s** — now last of six |
| String (Base64) | 2.9777s — last of six | **2.0153s** — now beats UInt8MultiArray |

Look at UInt8MultiArray: it takes **1.13 seconds longer** to send **34% less data**. That is
not a network effect — it is work the method does to itself.

**The reason is gluing.** `UInt8MultiArray` can only carry one long strip of bytes. Given four
separate blocks, it must first copy them all into a single strip, and that copying costs about
1.2 seconds no matter how fast the network is. On a slow link nobody would notice; on a
Gigabit cable it becomes the largest single cost.

String (Base64) does not escape cheaply either — it still makes the data 33% bigger — but 33%
of a smaller payload costs less than the gluing does, so it wins this round by default.

**The other four methods can carry several blocks side by side**, each keeping its own size
and shape, so they never glue anything. That is why all four finish between 1.09s and 1.48s
while the ROS 2 pair needs 2.0–4.1s.

The winner is unaffected: Arrow IPC leads both tests, at 93.5 MB/s on one block and
91.0 MB/s on four. Sending the same data in four pieces rather than one costs it under 3%.

### WiFi

WiFi results are **not reported here**. Only three of the six methods have been measured
over WiFi — the Arrow and gRPC methods have never been run on it — so no comparable table
can be built. The ROS 2 and BabyROS WiFi runs are written up separately in
**[README_wifi.md](README_wifi.md)**.

---

### How close to the wire?

The cable itself carries at most **118 MB/s** (TCP) or **120 MB/s** (UDP, which is what
ROS 2 uses). Comparing each method against that ceiling shows how much is lost to the method
rather than the network:

| Method | One big block | % of wire | Four blocks | % of wire |
| :--- | ---: | ---: | ---: | ---: |
| **Arrow IPC + TCP** | **93.5 MB/s** | **79%** | **91.0 MB/s** | **77%** |
| Arrow Flight (gRPC) | 87.4 MB/s | 74% | 85.6 MB/s | 73% |
| BabyROS (Zenoh) | 84.0 MB/s | 71% | 77.9 MB/s | 66% |
| gRPC String / repeated bytes | 69.2 MB/s | 59% | 69.3 MB/s | 59% |
| ROS2 UInt8MultiArray | 71.2 MB/s | 60% | 30.6 MB/s | 26% |
| ROS2 String (Base64) | 50.4 MB/s | 43% | 49.0 MB/s | 42% |

Nothing reaches the ceiling, and nothing should — every method has to read the numbers out of
memory, describe them, and hand them to the network card. Arrow IPC gives up the least, at
about a fifth.

Two rows are worth a second look:

* **UInt8MultiArray collapses to 26%** on four blocks — by far the worst figure in the table.
  That is the gluing cost: it spends more time copying blocks together than sending them.
* **String (Base64) sits near 43% on both.** Its loss is constant because its cause is
  constant: it always makes the data 33% bigger, whatever shape it is in.

These speeds exclude nothing — they are the full time from starting to prepare a message to
having it received, so they are directly comparable with the tables above.

---

## Detailed Results

Full per-experiment analysis, plots, and conclusions are in the two benchmark READMEs:

- **[README_wifi.md](README_wifi.md)** — WiFi experiments: same machine, X86→X86, X86→Jetson Nano
  - Single array: UInt8MultiArray vs String (Base64)
  - List of arrays: UInt8MultiArray vs String (Base64)

- **[README_ethernet.md](README_ethernet.md)** — Ethernet experiments: X86→X86, X86→Jetson Nano
  - Single array: UInt8MultiArray vs String (Base64)
  - List of arrays: UInt8MultiArray vs String (Base64)
  - Non-ROS: Arrow Flight vs Arrow IPC+TCP vs gRPC String

---

## Overall Recommendations

### Is there a single best option?

**Yes, over a cable: Arrow IPC + TCP.** It wins all four Ethernet tests — both machine
pairings, both data shapes.

| Place | One big block (X86→X86) | Four blocks (X86→X86) |
| :--- | :--- | :--- |
| 1 | **Arrow IPC + TCP** 1.6057s | **Arrow IPC + TCP** 1.0866s |
| 2 | Arrow Flight 1.7163s | Arrow Flight 1.1544s |
| 3 | BabyROS 1.7858s | BabyROS 1.2686s |
| 4 | UInt8MultiArray 2.1086s | gRPC 1.4255s |
| 5 | gRPC String 2.1671s | String (Base64) 2.0153s |
| 6 | String (Base64) 2.9777s | UInt8MultiArray 3.2343s |

The order of the top three is the same in both tests, and the gaps are small — Arrow IPC is
6% ahead of Arrow Flight and 11% ahead of BabyROS on one block. All three are far ahead of
anything from ROS 2.

**Why the simplest method wins.** Arrow Flight and gRPC wrap every message in extra
bookkeeping to manage the connection. That work is useful in general, but here it buys
nothing — there is one sender, one receiver, one big message — so it is pure cost. A plain
socket carrying the numbers as they already sit in memory has nothing to strip away.

**Choose something else when you need what it cannot do:**

| If you need… | Use | Cost |
| :--- | :--- | :--- |
| A sender that publishes to any number of receivers | **BabyROS** | 11% slower than Arrow IPC |
| A managed connection, retries, several clients | **Arrow Flight** | 6% slower |
| To stay inside ROS 2 (bags, launch files, tooling) | **UInt8MultiArray** for one block, **String** for several | 24–98% slower |

Arrow IPC and Arrow Flight both need the receiver to open a stream first; neither gives you
ROS-style topics where a sender simply broadcasts. That is what BabyROS's 11% buys.

### Start here: what constrains you?

| If this is true… | Use | Why |
| :--- | :--- | :--- |
| You **must** run inside ROS 2 (bags, launch files, introspection) | **UInt8MultiArray**, except a list of arrays on a fast link → **String (Base64)** | Only these two are actual ROS 2 message types |
| You want pub/sub semantics but **not** DDS | **BabyROS (Zenoh)** | Fastest ROS-style API tested; the only method immune to a slow receiver |
| You need raw minimum latency and no pub/sub | **Arrow IPC + TCP** | Fastest in all four Ethernet tests — 93.5 MB/s, 79% of what the cable can carry |
| Your receiver is **ARM / constrained** | **BabyROS** or **Arrow Flight** | Both hold ~95–104 MB/s on the Jetson; ROS 2 collapses to 39–42 MB/s |

### Best option per configuration

Measured winner in each cell, with the runner-up for context.

**Single 150 MB tensor**

| Configuration | Best | Runner-up | Margin |
| :--- | :--- | :--- | :--- |
| X86 → X86, Ethernet | **Arrow IPC + TCP** 1.6057s | Arrow Flight 1.7163s | 6% |
| X86 → Jetson, Ethernet | **Arrow IPC + TCP** 1.6648s | Arrow Flight 1.7235s | 3% |

**List of ~99 MB across four arrays**

| Configuration | Best | Runner-up | Margin |
| :--- | :--- | :--- | :--- |
| X86 → X86, Ethernet | **Arrow IPC + TCP** 1.0866s | Arrow Flight 1.1544s | 6% |
| X86 → Jetson, Ethernet | **Arrow IPC + TCP** 1.1063s | Arrow Flight 1.1667s | 5% |

### The three rules that explain every result

**1. Turning numbers into text makes them 33% bigger, and that never pays off.** The String
method is last of six on the one-big-block test. It only looks good once — on the four-blocks
test — and that is because its rival has an even worse problem (rule 2). Both still lose to
every non-ROS method.

**2. Gluing several blocks into one strip costs about 1.2 seconds, every time.**
`UInt8MultiArray` can only send one strip of bytes, so it must copy the four blocks together
first. That copying time does not shrink on a faster network, so on a cable it becomes the
biggest cost. Arrow and BabyROS can send the blocks separately and skip it entirely — which
is why all three non-ROS methods finish under 1.15s.

**3. ROS 2 gets much slower on a weak receiver; the others barely notice.** Swapping the
receiver from a PC to a Jetson Nano costs ROS 2 **70%** on one block (2.1086s → 3.5886s). It
costs Arrow IPC 4%, Arrow Flight 0%, and BabyROS 1%. This is the biggest single effect in the
study and it decides all the advice above about small devices.

<<<<<<< HEAD
=======

>>>>>>> refs/remotes/origin/main

---

## Repository Structure

```
.
├── README.md                          ← this file
├── README_wifi.md                     ← WiFi experiment details & plots
├── README_ethernet.md                 ← Ethernet experiment details & plots
│
├── iperf_outputs.zip                  ← iperf3 baseline: Ethernet UDP (100 runs)
├── iperf_tcp_outputs.zip              ← iperf3 baseline: Ethernet TCP (100 runs)
├── wifi_iperf_outputs.zip             ← iperf3 baseline: WiFi UDP + WiFi TCP (~98/96 runs)
│
├── string/                            ← ROS2 String (Base64), single array
├── uint8multiarray/                   ← ROS2 UInt8MultiArray, single array
├── string_list_numpy_array/           ← ROS2 String (Base64), list of arrays
├── uint8multiarray_list_numpy_array/  ← ROS2 UInt8MultiArray, list of arrays
├── arrow_flight/                      ← Non-ROS: Arrow Flight (gRPC)
├── arrow_ipc/                         ← Non-ROS: Arrow IPC + TCP
├── grpc_string/                       ← Non-ROS: gRPC bytes
├── babyros/                           ← Non-ROS: BabyROS (Zenoh), single array
├── babyros_list_numpy_array/          ← Non-ROS: BabyROS (Zenoh), list of arrays
├── babyros_client_server/             ← Non-ROS: BabyROS request/reply mode
├── arrow_flight_list_numpy_array/     ← Non-ROS: Arrow Flight, list of arrays
├── arrow_ipc_list_numpy_array/        ← Non-ROS: Arrow IPC + TCP, list of arrays
├── grpc_string_list_numpy_array/      ← Non-ROS: gRPC repeated bytes, list of arrays
│
└── analysis/
    ├── plot_analysis.py               ← generates WiFi plots
    ├── plot_analysis_ethernet.py      ← generates Ethernet plots
    ├── wifi/plots/                    ← single array WiFi plots
    ├── wifi/plots_2nd/                ← list of arrays WiFi plots
    ├── ethernet/plots/                ← single array Ethernet plots
    ├── ethernet/plots_2nd/            ← list of arrays Ethernet plots
    ├── ethernet/plots_non_ros/        ← non-ROS Ethernet plots
    ├── ethernet/plots_all/            ← all six methods, one big block
    ├── ethernet/plots_all_2nd/        ← all six methods, four blocks
    ├── {wifi,ethernet}/plots_babyros/     ← BabyROS vs ROS2, single array
    ├── ethernet/plots_list_non_ros/   ← Arrow IPC vs Flight vs BabyROS, list
    └── {wifi,ethernet}/plots_babyros_2nd/ ← BabyROS vs ROS2, list of arrays
```
