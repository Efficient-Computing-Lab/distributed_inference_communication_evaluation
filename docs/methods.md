# Methods and Implementation Notes

Detailed description of each communication method benchmarked in
[README.md](../README.md): what the technology is, what this repository actually
sends with it, and what it costs.

---

## Network Baseline (iperf3)

Raw network throughput was characterized using **iperf3** before any ROS 2 middleware overhead — establishing the available bandwidth ceiling for the link used in all experiments.

Each dataset consists of repeated 30-second iperf3 runs between the same client/server pair used in the ROS 2 benchmarks:

| Dataset | Source zip | Protocol | Valid runs |
| :--- | :--- | :--- | :--- |
| Ethernet UDP | `iperf_outputs.zip` | UDP | 100 |
| Ethernet TCP | `iperf_tcp_outputs.zip` | TCP | 100 |

### Ethernet

> All machines connected to a Gigabit switch. Client IP `147.102.19.162` → Server IP `147.102.19.67`.

| Protocol | Throughput sent (mean ± stdev) | Throughput recv (mean ± stdev) | RTT (mean) | Jitter (mean) | Packet loss | TCP retransmits |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **UDP** | 956.18 ± 0.25 Mbit/s | 956.15 ± 0.25 Mbit/s | — | 0.016 ms | 0.0004% | — |
| **TCP** | 942.01 ± 0.20 Mbit/s | 941.35 ± 0.12 Mbit/s | 1.96 ms | — | — | 0 (zero) |

The Ethernet link saturates at ~956 Mbit/s (UDP) / ~942 Mbit/s (TCP) with essentially no jitter, zero packet loss, and zero TCP retransmits across all 100 runs — a near-ideal Gigabit channel.

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
  This is why ROS 2's disadvantage grows on lossy or high-RTT links, where a single lost
  fragment stalls the whole sample.
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
+70%), and it is by far the **steadiest**: 0.013 s standard deviation on Ethernet→Jetson
where UInt8MultiArray shows 0.136 s — roughly 10× tighter on a mean that is already 2× lower.

**Two settings stock BabyROS does not apply** were required to get there, both documented in
[babyros/README.md](../babyros/README.md):

- **`CongestionControl.BLOCK`.** BabyROS declares its Zenoh publisher with no congestion
  setting, so Zenoh's default `DROP` applies: a 150 MB payload overflows the transmit queue
  and is **silently discarded** while `put()` returns cleanly and the publisher logs success.
  Delivery was ~20% same-machine and ~0% cross-machine until the publisher re-declared with
  `BLOCK`, which waits for queue space instead. It is 100% now; `--allow-drop` reproduces the
  original behaviour.
- **`wait_before_close = 60 s`.** How long a blocking publisher may wait for queue space
  before Zenoh tears down the transport session. The stock default is below the time a 150 MB
  payload needs on a saturated link, so the session was torn down mid-run. `rmw_zenoh` raises
  the same value for the same reason.

> `tcp_raw/` and `babyros_client_server/` also ship in this repo but have no recorded results
> and appear in no ranking — see [README.md](../README.md#running-the-benchmark).

---
