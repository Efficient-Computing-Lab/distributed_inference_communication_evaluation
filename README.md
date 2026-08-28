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

### ROS 2 (DDS / FastDDS middleware)

| Method | Serialization | Transmission size |
| :--- | :--- | :--- |
| **UInt8MultiArray** | Raw binary (`.tobytes()` / `np.frombuffer()`) | ~150 MB |
| **String (Base64)** | Base64 text encoding | ~200 MB (+33%) |

Each method is tested with two shapes of data, because they behave differently:

- **One big block** — a single 6125×6125 grid of numbers (150 MB). Like one large image.
- **Four smaller blocks** — four grids of different sizes, 99 MB in total. Like the several
  outputs a neural network produces at once.

The second shape matters because some methods can send several blocks side by side, while
others must first glue them into one long strip — and that gluing costs time.

### Non-ROS (Ethernet only)

| Method | Transport | Serialization |
| :--- | :--- | :--- |
| **Arrow Flight (gRPC)** | gRPC / HTTP2 | Apache Arrow IPC (columnar) |
| **Arrow IPC + TCP** | Raw TCP socket | Apache Arrow IPC (columnar) |
| **gRPC String (bytes)** | gRPC / HTTP2 | Protobuf `bytes` field |
| **BabyROS** | Zenoh | Raw numpy bytes + JSON manifest (NDAR/NDDC) |

[BabyROS](babyros/README.md) keeps a ROS-style pub/sub API but replaces DDS with Zenoh.
It is tested on both payload shapes (`babyros/`, `babyros_list_numpy_array/`).

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

### Caveats worth carrying

* Results were recorded under two different clock start points. The *comparable* columns correct for it; [Measurement validity](#measurement-validity) explains which conclusions are affected (few) and which are not (most).
* Only Ethernet is reported here. Three of the six methods have never been run over WiFi, so no comparable WiFi table exists; the ROS 2 and BabyROS WiFi runs are in [README_wifi.md](README_wifi.md).
* BabyROS needs Python 3.11–3.12 and glibc ≥ 2.28, which **rules out the Jetson Nano used here** without a container — see [babyros/README.md](babyros/README.md).

---

## Measurement validity

**Every Ethernet result was measured the same way**, so the tables can be compared directly.
The clock starts on the sender before the test data is created and stops when the receiver
has the message, which means each figure covers the whole path: making the payload, packing
it, and moving it.

That was not always true. Earlier runs used three different start points, which made Arrow
Flight look faster than it was. All 24 Ethernet cells have since been re-collected or
verified on the single shared basis, and every sender script now uses it.

**Two faults found and fixed while collecting:**

* **Files being appended, not replaced.** The scripts add to an existing CSV rather than
  overwriting it, so restarting a run silently joined two sessions into one file. Three files
  were affected and have been split by timestamp. Always delete the CSV before re-running:
  `rm -f <folder>/*.csv`
* **Truncated headers after copying between machines.** Two files arrived with `sg_id`
  instead of `msg_id` — a single missing leading byte. The plotting script skips such a file
  silently, so it looks like a missing experiment rather than a broken one. Worth checking
  after any transfer: `head -1 <file>` should start with `msg_id`.

**Still to collect:** no Arrow or gRPC method has been run over WiFi, so the WiFi tables
compare three methods rather than six.

One caveat no re-run fixes: latency is the receiver's clock minus the sender's clock, so if
the two machines' clocks drift apart every figure carries a fixed offset. It cancels out when
comparing methods on the same pair, so the rankings hold — but check `timedatectl` on both
machines before quoting absolute seconds.

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
