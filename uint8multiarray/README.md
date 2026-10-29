# ROS 2 UInt8MultiArray — one 150 MB array

Part of the [Large-Data Communication Benchmark](../README.md) — see the main README for
the full comparison, and [`docs/methods.md`](../docs/methods.md) for the method index.

| | |
| :--- | :--- |
| Message type | `std_msgs/UInt8MultiArray` |
| Middleware | ROS 2 Jazzy / eProsima Fast DDS (`rmw_fastrtps_cpp`) |
| Payload | one 6125×6125 `float32` array (~150 MB) |
| Serialization | raw binary — `.tobytes()` / `np.frombuffer()` |
| Four-array variant | [`../uint8multiarray_list_numpy_array/`](../uint8multiarray_list_numpy_array/README.md) |

## How it works

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
  addresses configured — and it is genuine work the non-ROS methods never do.

Neither ROS 2 message type understands numpy, so both methods flatten the array to bytes and
prepend a 12-byte header (`struct.pack('=Id', msg_id, publish_time)`) carrying the message
identity and send timestamp. Both publish on `big_topic` with queue depth 10.

### UInt8MultiArray — raw bytes down a byte-array message

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

## Running

ROS 2 Jazzy + `numpy`. Both machines need the same `ROS_DOMAIN_ID`; start the **subscriber
first**, run both sides from inside `uint8multiarray/`, and collect ~100 messages (5 s apart,
~9 minutes) before stopping both with `Ctrl-C`.

```bash
source /opt/ros/jazzy/setup.bash
export ROS_DOMAIN_ID=0            # on both machines
cd uint8multiarray
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

**Over TCP instead of UDP.** Fast DDS over TCP does not handle these payloads; see
[ROS 2 over TCP](../README.md#ros-2-over-tcp) for the measurements. To reproduce, from the
repo root:

```bash
python3 collect.py receiver uint8multiarray ethernet_tcp/diff_machines --transport tcp
python3 collect.py sender   uint8multiarray ethernet_tcp/diff_machines --transport tcp --peer <receiver ip>
```

### Folder naming

`--folder` encodes the machine pair: `ethernet/x86_machines` for X86 → X86 and
`ethernet/diff_machines` for X86 → Jetson Nano. Use these exact names to extend the existing
results — every method uses the same two. TCP runs use the same names under
`ethernet_tcp/`.

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
