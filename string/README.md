# ROS 2 String (Base64) — one 150 MB array

Part of the [Large-Data Communication Benchmark](../README.md) — see the main README for
the full comparison, and [`docs/methods.md`](../docs/methods.md) for the method index.

| | |
| :--- | :--- |
| Message type | `std_msgs/String` |
| Middleware | ROS 2 Jazzy / eProsima Fast DDS (`rmw_fastrtps_cpp`) |
| Payload | one 6125×6125 `float32` array (~150 MB → ~200 MB on the wire) |
| Serialization | Base64 text encoding (+33%) |
| Four-array variant | [`../string_list_numpy_array/`](../string_list_numpy_array/README.md) |

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

### String (Base64) — bytes as text

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

## Running

ROS 2 Jazzy + `numpy`. Both machines need the same `ROS_DOMAIN_ID`; start the **subscriber
first**, run both sides from inside `string/`, and collect ~100 messages (5 s apart,
~9 minutes) before stopping both with `Ctrl-C`.

```bash
source /opt/ros/jazzy/setup.bash
export ROS_DOMAIN_ID=0            # on both machines
cd string
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

**Over TCP instead of UDP** (on both machines; see
[ROS 2 over TCP](../README.md#ros-2-over-tcp)):

```bash
export FASTDDS_BUILTIN_TRANSPORTS=LARGE_DATA
python3 subscriber.py --folder ethernet_tcp/x86_machines   # receiving X86
python3 publisher.py  --folder ethernet_tcp/x86_machines   # sending X86
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
