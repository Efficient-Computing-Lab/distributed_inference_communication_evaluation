# Large-Data Communication Benchmark

How fast can a machine transmit a large numerical array to another machine? This repository
includes six transmission methods, two ROS 2 message types and four non-ROS transports. The network has sending
Gigabit speed and we use two PCs and a Jetson Nano.

Tested methods — each folder's README describes the technology, what it sends, and how to
run it:

| Method | One 150 MB array | Four arrays, ~99 MB |
| :--- | :--- | :--- |
| ROS 2 UInt8MultiArray | [`uint8multiarray/`](uint8multiarray/README.md) | [`uint8multiarray_list_numpy_array/`](uint8multiarray_list_numpy_array/README.md) |
| ROS 2 String / Base64 | [`string/`](string/README.md) | [`string_list_numpy_array/`](string_list_numpy_array/README.md) |
| Arrow IPC + TCP | [`arrow_ipc/`](arrow_ipc/README.md) | [`arrow_ipc_list_numpy_array/`](arrow_ipc_list_numpy_array/README.md) |
| Arrow Flight | [`arrow_flight/`](arrow_flight/README.md) | [`arrow_flight_list_numpy_array/`](arrow_flight_list_numpy_array/README.md) |
| gRPC | [`grpc_string/`](grpc_string/README.md) | [`grpc_string_list_numpy_array/`](grpc_string_list_numpy_array/README.md) |
| BabyROS / Zenoh | [`babyros/`](babyros/README.md) | [`babyros_list_numpy_array/`](babyros_list_numpy_array/README.md) |

## Experimental Setup

- Network: Gigabit Ethernet, ~118 MB/s TCP / ~120 MB/s UDP ceiling (iperf3, 100 runs)
- Sender: x86
- Receivers: x86 and Jetson Nano
- Payloads:
  - one 150 MB array (6125×6125)
  - four arrays, ~99 MB total
- Metric: end-to-end transfer time — the clock starts before the array is created and stops
  when the receiver holds it again, so each figure includes the method's own packing cost.
  100 messages per configuration.

## Results

Method names link to that method's folder README; the four-array runs live in the
corresponding `*_list_numpy_array/` folder.

| Method | 150 MB<br>x86 → x86 | 150 MB<br>x86 → Jetson | 4 arrays<br>x86 → x86 | 4 arrays<br>x86 → Jetson |
| :--- | ---: | ---: | ---: | ---: |
| [**Arrow IPC + TCP**](arrow_ipc/README.md) | **1.606** | **1.665** | **1.087** | **1.106** |
| [Arrow Flight (gRPC)](arrow_flight/README.md) | 1.716 | 1.724 | 1.154 | 1.167 |
| [BabyROS (Zenoh)](babyros/README.md) | 1.786 | 1.799 | 1.269 | 1.265 |
| [ROS 2 UInt8MultiArray](uint8multiarray/README.md) | 2.109 | 3.589 | 3.234 | 4.149 |
| [gRPC (bytes / repeated bytes)](grpc_string/README.md) | 2.167 | 2.233 | 1.426 | 1.479 |
| [ROS 2 String (Base64)](string/README.md) | 2.978 | 5.082 | 2.015 | 3.307 |

## Key Findings

- Arrow IPC + TCP achieved the best overall transfer performance.
- Arrow Flight provided similar performance with a managed client/server interface.
- BabyROS/Zenoh performed well when pub/sub semantics were required. Its ~11% deficit to
  Arrow IPC is not a Zenoh transport limit but two payload copies forced by zenoh-python's
  `ZBytes`. Arrays *are* carried natively as raw bytes; what is missing is a zero-copy
  handoff, since `ZBytes` accepts no buffer protocol and so must be given a materialised
  `bytes` object — see [the payload copy tax](babyros/README.md#the-payload-copy-tax).
- ROS 2 showed substantially larger overhead on the Jetson Nano.
- The tested UInt8MultiArray concatenation strategy performed poorly for multiple arrays.

## Recommendation

| If you need… | Use |
| :--- | :--- |
| Minimum latency, point-to-point | [**Arrow IPC + TCP**](arrow_ipc/README.md) |
| A managed connection, several clients | [**Arrow Flight**](arrow_flight/README.md) (~6% slower) |
| Pub/sub without DDS | [**BabyROS (Zenoh)**](babyros/README.md) (~11% slower) |
| To stay inside ROS 2 | [**UInt8MultiArray**](uint8multiarray/README.md) for one array, [**String (Base64)**](string/README.md) for several |

## Running the Benchmark

Every experiment follows the same shape: **start the receiver first, then the sender**, run
both from inside the method's directory, and let each run collect ~100 messages (5 s apart,
so ~9 minutes) before stopping both sides with `Ctrl-C`. Each side writes its own CSV into
`--folder`; latency is computed on the receiver.

Per-method detail — options, tuning profiles, ports and caveats — is in each folder's own
README, linked from the method table at the top of this file.

### Environment

| Method | Requirements |
| :--- | :--- |
| ROS 2 (`string`, `uint8multiarray`, `*_list_numpy_array`) | ROS 2 Jazzy + `numpy` — `source /opt/ros/jazzy/setup.bash`, same `ROS_DOMAIN_ID` on both sides |
| `arrow_ipc`, `arrow_flight` | `conda env create -f arrow_flight/environment.yml` (numpy + pyarrow) |
| `grpc_string` | `conda env create -f grpc_string/environment.yml` (`*_pb2*.py` are pre-generated) |
| `babyros` | Python 3.11–3.12 venv — see [babyros/README.md](babyros/README.md) |
| `analysis/` | `pip install -r analysis/requirements.txt` |

### Folder naming

`--folder` encodes the machine pair. Use these exact names to extend the existing results —
every method uses the same two:

| Machine pair | `--folder` |
| :--- | :--- |
| X86 → X86 | `ethernet/x86_machines` |
| X86 → Jetson Nano | `ethernet/diff_machines` |

The commands below all use `ethernet/x86_machines`; repeat each one with
`ethernet/diff_machines` when the receiver is the Jetson Nano. Twelve runs in total —
six methods × two payload shapes — per machine pair.

### ROS 2 methods

Subscriber first, on the receiving machine. Both sides need the same `ROS_DOMAIN_ID`.
Folder READMEs: [`uint8multiarray/`](uint8multiarray/README.md),
[`uint8multiarray_list_numpy_array/`](uint8multiarray_list_numpy_array/README.md),
[`string/`](string/README.md),
[`string_list_numpy_array/`](string_list_numpy_array/README.md).

```bash
export ROS_DOMAIN_ID=0            # on both machines

# one 150 MB array
cd uint8multiarray                 # and: cd string
python3 subscriber.py --folder ethernet/x86_machines   # receiver
python3 publisher.py  --folder ethernet/x86_machines   # sender

# four arrays, ~99 MB
cd uint8multiarray_list_numpy_array   # and: cd string_list_numpy_array
python3 subscriber.py --folder ethernet/x86_machines
python3 publisher.py  --folder ethernet/x86_machines
```

`string/` and `uint8multiarray/` also ship a `custom_fast_dds.xml` tuning profile (async
publish, 2 GB socket buffers). It is **not** applied automatically and no recorded result
uses it; to enable it, export the path on **both** sides before launching:

```bash
export FASTRTPS_DEFAULT_PROFILES_FILE=$PWD/custom_fast_dds.xml
```

#### ROS 2 over TCP

All recorded ROS 2 results use stock Fast DDS, which carries data as RTPS over **UDPv4**.
To repeat them over **TCP**, switch Fast DDS to its `LARGE_DATA` builtin transport on
**both** machines. Discovery stays on UDP multicast, so no addresses need configuring, but
every sample travels over a TCPv4 connection. Results go to `ethernet_tcp/` so the UDP
results in `ethernet/` are never overwritten:

```bash
export RMW_IMPLEMENTATION=rmw_fastrtps_cpp
export FASTDDS_BUILTIN_TRANSPORTS=LARGE_DATA   # on both machines
unset FASTRTPS_DEFAULT_PROFILES_FILE           # a profile could override it

cd uint8multiarray      # and the other three ROS 2 folders
python3 subscriber.py --folder ethernet_tcp/x86_machines   # receiver
python3 publisher.py  --folder ethernet_tcp/x86_machines   # sender
```

`collect.py` does the same with `--transport tcp`. It also writes `sender_env.txt` /
`receiver_env.txt` next to the CSVs to record the transport, and it refuses to write TCP
results outside a `*_tcp` folder:

```bash
python3 collect.py receiver uint8multiarray ethernet_tcp/x86_machines --transport tcp
python3 collect.py sender   uint8multiarray ethernet_tcp/x86_machines --transport tcp
```

To confirm a run really used TCP, `ss -tnp | grep python3` on either machine should show an
established connection while messages are flowing.

### Arrow IPC + TCP, Arrow Flight, gRPC

Server first, on the sending machine; `--host` on the client is the server's address.
All three accept `--port` if the default is taken. Folder READMEs:
[`arrow_ipc/`](arrow_ipc/README.md),
[`arrow_ipc_list_numpy_array/`](arrow_ipc_list_numpy_array/README.md),
[`arrow_flight/`](arrow_flight/README.md),
[`arrow_flight_list_numpy_array/`](arrow_flight_list_numpy_array/README.md),
[`grpc_string/`](grpc_string/README.md),
[`grpc_string_list_numpy_array/`](grpc_string_list_numpy_array/README.md).

```bash
# Arrow IPC + TCP — port 9000
cd arrow_ipc                       # four arrays: cd arrow_ipc_list_numpy_array
python3 server.py --folder ethernet/x86_machines                    # sender
python3 client.py --folder ethernet/x86_machines --host <server-ip> # receiver

# Arrow Flight — port 8815
cd arrow_flight                    # four arrays: cd arrow_flight_list_numpy_array
python3 server.py --folder ethernet/x86_machines
python3 client.py --folder ethernet/x86_machines --host <server-ip>

# gRPC — port 50051
cd grpc_string                     # four arrays: cd grpc_string_list_numpy_array
python3 server.py --folder ethernet/x86_machines
python3 client.py --folder ethernet/x86_machines --host <server-ip>
```

### BabyROS (Zenoh)

Folder READMEs: [`babyros/`](babyros/README.md) — which also covers installation and the
ARM/Jetson constraints — and
[`babyros_list_numpy_array/`](babyros_list_numpy_array/README.md).

Subscriber first. Peers on the same subnet find each other by multicast scouting; where
multicast is blocked, pass `--listen tcp/0.0.0.0:7447` on the publisher and
`--connect tcp/<publisher-ip>:7447` on the subscriber (`python3 babyros/net_check.py`
verifies connectivity).

```bash
cd babyros                         # four arrays: cd babyros_list_numpy_array
python3 subscriber.py --folder ethernet/x86_machines   # receiver
python3 publisher.py  --folder ethernet/x86_machines   # sender
```

The publisher applies `CongestionControl.BLOCK` and `wait_before_close = 60 s`; without them
Zenoh silently drops 150 MB payloads. `--allow-drop` reproduces the stock behaviour.

### Network baseline (iperf3)

Run from the publisher machine. Requires `iperf3` on both hosts and SSH access to the remote:

```bash
python3 udp_test.py --ip <remote-ip> --remote_user <remote-user> --trials 100 --duration 30
python3 tcp_test.py --ip <remote-ip> --remote_user <remote-user> --trials 100 --duration 30
```

Each writes a timestamped folder with per-run JSON, both machines' specs, and `summary.json`.

### Plots and verification

```bash
cd analysis
python3 plot_analysis_ethernet.py     # → ethernet/plots{,_2nd,_non_ros,...}/
```

The plotting script reads the subscriber CSVs directly and fails if a configuration has not
been collected yet. Sent and received counts should match — a gap means messages were
dropped and the latency figures are survivorship-biased:

```bash
wc -l <method>/ethernet/<pair>/publisher_log.csv <method>/ethernet/<pair>/subscriber_log.csv
```

## Detailed Analysis

For detailed results, plots and implementation discussion:
- [README_ethernet.md](README_ethernet.md) — per-experiment results and plots
- [docs/methods.md](docs/methods.md) — network baseline, comparison methodology, and the
  index of per-method descriptions
- [analysis/](analysis/) — plotting scripts and generated figures

## Repository Structure

```
.
├── README.md                    ← this file
├── README_ethernet.md           ← Ethernet experiment details & plots
├── docs/methods.md              ← method-by-method technical discussion
├── iperf_*.zip                  ← iperf3 network baselines
│
├── string/                      ← ROS 2 String (Base64)
├── uint8multiarray/             ← ROS 2 UInt8MultiArray
├── arrow_ipc/                   ← Arrow IPC + TCP
├── arrow_flight/                ← Arrow Flight (gRPC)
├── grpc_string/                 ← gRPC bytes
├── babyros/                     ← BabyROS (Zenoh)
├── *_list_numpy_array/          ← same methods, four-array payload
│                                  (every method folder has its own README.md)
│
└── analysis/                    ← plotting scripts and figures
```

Every method folder carries its own `README.md` with the technology description, the run
commands for both machine pairs, and that configuration's results — linked from the method
table at the top of this file.
