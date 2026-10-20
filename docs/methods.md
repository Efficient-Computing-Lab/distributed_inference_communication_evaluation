# Methods and Implementation Notes

Cross-cutting notes for the benchmark in [README.md](../README.md): the measured network
baseline, how the six methods are compared, and an index of the per-method descriptions —
each of which lives in its own folder alongside the code it describes.

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

### Method descriptions

Each method's full description — what the technology is, what this benchmark actually sends
with it, what it costs, and how to run both machine-pair scenarios — lives in that method's
own folder:

| Method | One 150 MB array | Four arrays, ~99 MB |
| :--- | :--- | :--- |
| ROS 2 UInt8MultiArray | [`uint8multiarray/`](../uint8multiarray/README.md) | [`uint8multiarray_list_numpy_array/`](../uint8multiarray_list_numpy_array/README.md) |
| ROS 2 String (Base64) | [`string/`](../string/README.md) | [`string_list_numpy_array/`](../string_list_numpy_array/README.md) |
| Arrow IPC + TCP | [`arrow_ipc/`](../arrow_ipc/README.md) | [`arrow_ipc_list_numpy_array/`](../arrow_ipc_list_numpy_array/README.md) |
| Arrow Flight | [`arrow_flight/`](../arrow_flight/README.md) | [`arrow_flight_list_numpy_array/`](../arrow_flight_list_numpy_array/README.md) |
| gRPC (protobuf bytes) | [`grpc_string/`](../grpc_string/README.md) | [`grpc_string_list_numpy_array/`](../grpc_string_list_numpy_array/README.md) |
| BabyROS (Zenoh) | [`babyros/`](../babyros/README.md) | [`babyros_list_numpy_array/`](../babyros_list_numpy_array/README.md) |

### ROS 2 (DDS / FastDDS middleware)

| Method | Serialization | Transmission size | Directory |
| :--- | :--- | :--- | :--- |
| **UInt8MultiArray** | Raw binary (`.tobytes()` / `np.frombuffer()`) | ~150 MB | [`uint8multiarray/`](../uint8multiarray/README.md), [`uint8multiarray_list_numpy_array/`](../uint8multiarray_list_numpy_array/README.md) |
| **String (Base64)** | Base64 text encoding | ~200 MB (+33%) | [`string/`](../string/README.md), [`string_list_numpy_array/`](../string_list_numpy_array/README.md) |

Both delegate to DDS: RTPS over UDP with `DATA_FRAG` fragmentation and reassembly, CDR
serialization, and multicast discovery with QoS matching. That discovery is what gives ROS 2
its best feature — a publisher that broadcasts to anyone listening, with no addresses
configured — and it is genuine work the non-ROS methods never do. Neither message type
understands numpy, so both flatten the array to bytes and prepend a 12-byte header
(`struct.pack('=Id', msg_id, publish_time)`); both publish on `big_topic` with queue depth 10.
Full discussion in each folder's README.

### Non-ROS (Ethernet only)

| Method | Transport | Serialization | Directory |
| :--- | :--- | :--- | :--- |
| **Arrow IPC + TCP** | Raw TCP socket | Apache Arrow IPC (columnar) | [`arrow_ipc/`](../arrow_ipc/README.md), [`arrow_ipc_list_numpy_array/`](../arrow_ipc_list_numpy_array/README.md) |
| **Arrow Flight (gRPC)** | gRPC / HTTP2 | Apache Arrow IPC (columnar) | [`arrow_flight/`](../arrow_flight/README.md), [`arrow_flight_list_numpy_array/`](../arrow_flight_list_numpy_array/README.md) |
| **gRPC String (bytes)** | gRPC / HTTP2 | Protobuf `bytes` field | [`grpc_string/`](../grpc_string/README.md), [`grpc_string_list_numpy_array/`](../grpc_string_list_numpy_array/README.md) |
| **BabyROS** | Zenoh | Raw numpy bytes + JSON manifest ([no schemas — six runtime-dispatched tags](../babyros/README.md#message-formats)) | [`babyros/`](../babyros/README.md), [`babyros_list_numpy_array/`](../babyros_list_numpy_array/README.md) |

Three of the four are **server-first and point-to-point**: the receiver connects to a stream
and the sender pushes a message every 5 s. That is a weaker guarantee than ROS 2 topics —
nobody discovers anybody, and there is one receiver — but it also removes discovery and
per-sample negotiation from the measured path. BabyROS is the exception: it keeps broadcast
pub/sub.
