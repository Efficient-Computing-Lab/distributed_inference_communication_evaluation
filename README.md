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

### Single numpy array (150 MB) — Ethernet

Every method is shown on the **same basis**: the clock starts before the test data is
created, which is how most of the runs were recorded. The four newer methods have that
creation time added back so they line up — the adjustment is shown in brackets. See
[Measurement validity](#measurement-validity).

| Method | X86 → X86 | X86 → Jetson Nano | Adjusted by |
| :--- | ---: | ---: | :--- |
| **Arrow IPC + TCP** | **1.6057s** | **1.6648s** | — |
| Arrow Flight (gRPC) | 1.8901s | 1.9472s | +0.500s |
| BabyROS (Zenoh) | 1.9660s | 1.9602s | +0.376s |
| ROS2 UInt8MultiArray | 2.1086s | 3.5886s | — |
| gRPC String (bytes) | 2.1671s | 2.2333s | — |
| ROS2 String (Base64) | 2.9777s | 5.0823s | — |

**Arrow IPC is fastest.** Its raw stopwatch time looked mid-table before, because Arrow
Flight's clock had been started late — skipping ~0.124s of packing that every other method
counted — while Arrow IPC's included the full ~0.376s of data creation. Once both are
measured the same way the gap is clear, and it matches what the four-block test shows on its
own.

**The receiving computer matters more than anything else.** Swapping the receiver from a
normal PC to a small Jetson Nano board makes the two ROS 2 methods about **70% slower**,
because ROS 2 does a lot of work on the receiving side and the small board struggles with
it. BabyROS shows no slowdown at all (1.9660s → 1.9602s), and the Arrow and gRPC methods
lose only 3–4%. This single effect drives most of the advice further down.

**Turning numbers into text is always a losing trade.** The String method encodes the data
as text, which makes it 33% bigger. It finishes last in both cases — the extra size costs
more than the encoding ever saves.

---

### List of numpy arrays (~99 MB) — Ethernet

All five on the same basis. The three newer methods have the ~0.232s of data-creation time
added back.

| Method | X86 → X86 | X86 → Jetson Nano | Adjusted by | Steadiness |
| :--- | ---: | ---: | :--- | ---: |
| **Arrow IPC + TCP** | **1.1966s** | **1.2288s** | +0.232s | **±0.0060s** |
| Arrow Flight (gRPC) | 1.2620s | 1.2614s | +0.232s | ±0.0094s |
| BabyROS (Zenoh) | 1.3717s | 1.3698s | +0.232s | ±0.0094s |
| ROS2 String (Base64) | 2.0153s | 3.3067s | — | ±0.0276s |
| ROS2 UInt8MultiArray | 3.2343s | 4.1493s | — | ±0.0222s |
| gRPC (repeated bytes) | not collected | not collected | — | — |

**Gluing the four blocks together costs about 1.2 seconds.** `UInt8MultiArray` can only send
one long strip of bytes, so it has to copy the four blocks into one first. On a fast cable
that copying takes longer than the extra data String sends — which is why String (2.0153s)
beats it (3.2343s) here, the only place String is not last.

**The three non-ROS methods never do that copying.** They carry the four blocks separately,
each keeping its own size and shape. All three finish between 1.20s and 1.37s, against
2.0–4.1s for ROS 2.

---

### Single numpy array (150 MB) — WiFi

| Method | X86 → X86 | X86 → Jetson Nano | Change on ARM |
| :--- | ---: | ---: | :--- |
| **BabyROS (Zenoh)** | **6.4182s** (±2.38) | **5.7376s** (±0.49) | none |
| ROS2 UInt8MultiArray | 8.6934s (±2.22) | 16.3764s (±4.34) | **+88%** |
| ROS2 String (Base64) | 11.0463s (±2.58) | 24.8816s (±5.25) | **+125%** |
| Arrow Flight / Arrow IPC / gRPC | not collected | not collected | — |

*BabyROS has +0.376s of data-creation time added so it sits on the same basis as the ROS 2
rows. It still wins comfortably — the gaps here are whole seconds.*

### List of numpy arrays (~99 MB) — WiFi

| Method | X86 → X86 | X86 → Jetson Nano | Std dev (X86) |
| :--- | ---: | ---: | ---: |
| **ROS2 UInt8MultiArray** | **8.3911s** | **12.9736s** | **0.6709** |
| BabyROS (Zenoh) | 10.5204s | not collected | 1.2756 |
| ROS2 String (Base64) | 10.5983s | 18.7159s | 1.3949 |
| Arrow Flight / Arrow IPC / gRPC | not collected | not collected | — |

*BabyROS has +0.232s added to match the ROS 2 basis. It still loses to UInt8MultiArray, and
now sits almost level with String (10.5204s vs 10.5983s).*

**No non-ROS method other than BabyROS has ever been run on WiFi**, so these two tables
compare three methods, not six. They are not equivalent to the Ethernet tables above and
should not be read as a like-for-like ranking across all methods.

**The small board suffers even more over WiFi.** On a cable the Jetson made ROS 2 about 70%
slower; over WiFi it makes it **88–125% slower**. WiFi drops far more packets than a cable
(0.065% against 0.0004%), and ROS 2 has to resend them — work the small board is bad at.
BabyROS does the opposite: it is actually *faster* to the Jetson (5.7376s) than to a PC
(6.4182s), and its timings barely wobble (±0.49s) where UInt8MultiArray swings by ±4.34s.

**Over WiFi, the shape of the data changes the winner.** BabyROS wins the one-big-block test
by 26–65%, but loses the four-blocks test to `UInt8MultiArray` (8.3911s vs 10.5204s) — the
only place in this whole study where a ROS 2 method beats it. WiFi is so much slower than a
cable that the 1.2s of gluing no longer matters, and ROS 2 copes with the dropped packets
better.

Full WiFi analysis and plots: **[README_wifi.md](README_wifi.md)**.

### Non-ROS alternatives (Ethernet only, 150 MB single array)

Transfer speed in MB/s is computed as `payload_bytes / transfer_time`. The network ceiling is the iperf3 baseline for each method's transport: **118 MB/s (TCP)** for Arrow-based and gRPC methods, **120 MB/s (UDP)** for ROS2/DDS methods (FastDDS uses UDP by default).

| Method | Transport | X86 → X86 | MB/s | X86 → Jetson Nano | MB/s |
| :--- | :--- | :--- | :--- | :--- | :--- |
| Network ceiling | TCP | — | **118 MB/s** | — | **118 MB/s** |
| Network ceiling | UDP | — | **120 MB/s** | — | **120 MB/s** |
| **Arrow Flight (gRPC)** | TCP | **1.3901s** ᵃ | **108 MB/s** | **1.4472s** ᵃ | **104 MB/s** |
| **BabyROS (Zenoh)** | TCP | 1.5900s ᵇ | 94 MB/s | **1.5842s** ᵇ | **95 MB/s** |
| **Arrow IPC + TCP** | TCP | 1.6057s | 93 MB/s | 1.6648s | 90 MB/s |
| **gRPC String (bytes)** | TCP | 2.1671s | 69 MB/s | 2.2333s | 67 MB/s |
| ROS2 UInt8MultiArray *(reference)* | UDP | 2.1086s | 71 MB/s | 3.5886s | 42 MB/s |
| ROS2 String (Base64) *(reference)* | UDP | 2.9777s | 67 MB/s | 5.0823s | 39 MB/s |

**Arrow Flight moves data at 104–108 MB/s, just 10–14 MB/s short of what the raw link can carry** — the gap is pure protocol overhead (gRPC/HTTP2 framing + Arrow serialization). ROS2 on X86 reaches 67–71 MB/s (~60% of the link), and on the Jetson Nano drops to 39–42 MB/s (~33%), because DDS middleware degrades disproportionately on constrained ARM hardware while TCP/gRPC connections are largely unaffected.

**BabyROS is the only method whose throughput does not change with the receiver** — 94 MB/s to an X86 and 95 MB/s to the Jetson Nano. Every other method loses ground on ARM (Arrow Flight 108 → 104, Arrow IPC 93 → 90, ROS2 71 → 42). It ranks second overall on X86 and second on the Jetson, while being the only non-ROS option here that keeps a publisher/subscriber API.

> ᵃ Arrow Flight and ᵇ BabyROS are shown here as originally recorded, not on the shared basis
> used elsewhere in this README — the MB/s column divides by pure transfer time, so adding
> data-creation time back would distort it. For latency comparisons use the table above.
>
> **This table is the single 150 MB array only.** On the ~99 MB list payload the ranking
> inverts — Arrow IPC + TCP leads at 102.5 MB/s, ahead of Arrow Flight. See the list results
> above.
>
> Two measurement caveats when reading this table. Arrow Flight stamps its send time *after* building the Arrow batch, so it excludes ~0.12–0.18s of serialization that Arrow IPC and BabyROS both include — the real gap between the top three is smaller than it appears. And the two ROS2 rows were collected before the timing convention was unified, so they still include ~0.376s of payload generation; corrected, UInt8MultiArray on X86 lands nearer 1.73s (87 MB/s).

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

*Tests where both programs ran on one computer are left out here — no data crosses a
network in that case, so they answer a different question.*

**Arrow IPC + TCP wins all four Ethernet tests once every method is timed the same way. No
ROS 2 method wins any of them.**

| Method | Ethernet tests won (of 4) |
| :--- | :--- |
| **Arrow IPC + TCP** | **4** — both four-block tests outright, both one-block tests after correction |
| Arrow Flight (gRPC) | 0 — leads the raw stopwatch on one-block, but only because its clock started late |
| BabyROS (Zenoh) | 0 — second or third throughout |
| UInt8MultiArray / String | **0** |

The four-blocks results are the only fully fair comparison we have. Arrow IPC, Arrow Flight
and BabyROS were all timed the same way, so none of them gets an unfair head start:

| Ethernet, four blocks | X86 → X86 | X86 → Jetson |
| :--- | ---: | ---: |
| **Arrow IPC + TCP** | **1.1966s** (±0.0060) | **1.2288s** (±0.0535) |
| Arrow Flight (gRPC) | 1.2620s (±0.0094) | 1.2614s (±0.0134) |
| BabyROS (Zenoh) | 1.3717s (±0.0094) | 1.3698s (±0.0121) |

Setting the data-creation time aside, Arrow IPC moves the data at **102.5 MB/s**. The cable
itself can carry at most 118 MB/s, so it is using **87%** of what the wire allows — and its timings are the steadiest of anything
here, varying by only ±0.0060s across 100 messages.

Why does the simplest method win? Arrow Flight and gRPC wrap every message in extra
bookkeeping. On the 150 MB test that cost is spread thin and barely shows. On the smaller
98.84 MB test there is less data to spread it over, so it starts to hurt — and a plain
network socket wins instead. The order flips between the two tests for that reason alone.

**Arrow Flight's apparent lead on the one-block test was a timing artefact.** Its clock
started after packing was already done, skipping ~0.124s that every other method counted. On
the shared basis it is **1.8901s**, behind Arrow IPC's 1.6057s. See
[Measurement validity](#measurement-validity).

BabyROS does not win any Ethernet test, but it is still the one to pick if you want the
ROS-style way of working, where a sender just publishes and any number of receivers can
subscribe. Both Arrow methods work differently: the receiver has to ask for a stream first.
BabyROS is also the only method that runs at exactly the same speed whichever receiver you
use — 1.9660s to a PC, 1.9602s to the small Jetson board.

**Take one of the two exceptions instead when:**

| Condition | Use | Margin over BabyROS |
| :--- | :--- | :--- |
| Four blocks, Ethernet | **Arrow IPC + TCP** | 13% faster |
| One big block, Ethernet, pub/sub not needed | **Arrow IPC + TCP** | 18% faster |

One practical catch before choosing BabyROS: it needs Python 3.11 or 3.12 and a fairly
recent Linux. **A stock Jetson Nano has neither**, so it can only run BabyROS inside a
container.

### Start here: what constrains you?

| If this is true… | Use | Why |
| :--- | :--- | :--- |
| You **must** run inside ROS 2 (bags, launch files, introspection) | **UInt8MultiArray**, except a list of arrays on a fast link → **String (Base64)** | Only these two are actual ROS 2 message types |
| You want pub/sub semantics but **not** DDS | **BabyROS (Zenoh)** | Fastest ROS-style API tested; the only method immune to a slow receiver |
| You need raw minimum latency and no pub/sub | **Arrow IPC + TCP** for a list of arrays, **Arrow Flight** for a single tensor | Arrow IPC hits 102.5 MB/s on the list payload with the tightest jitter measured |
| Your receiver is **ARM / constrained** | **BabyROS** or **Arrow Flight** | Both hold ~95–104 MB/s on the Jetson; ROS 2 collapses to 39–42 MB/s |

### Best option per configuration

Measured winner in each cell, with the runner-up for context.

**Single 150 MB tensor**

| Configuration | Best | Runner-up | Margin |
| :--- | :--- | :--- | :--- |
| X86 → X86, Ethernet | **Arrow IPC + TCP** 1.6057s | Arrow Flight 1.8901s | 15% |
| X86 → Jetson, Ethernet | **Arrow IPC + TCP** 1.6648s | Arrow Flight 1.9472s | 15% |

**List of ~99 MB across four arrays**

| Configuration | Best | Runner-up | Margin |
| :--- | :--- | :--- | :--- |
| X86 → X86, Ethernet | **Arrow IPC + TCP** 1.1966s | Arrow Flight 1.2620s | 5.2% |
| X86 → Jetson, Ethernet | **Arrow IPC + TCP** 1.2288s | Arrow Flight 1.2614s | 2.6% |

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
receiver from a PC to a Jetson Nano costs ROS 2 about 70% (2.11s → 3.59s). It costs BabyROS
nothing measurable (1.9660s → 1.9602s) and Arrow Flight about 4%. This is the biggest single
effect in the whole study, and it decides all the advice above about small devices.

### Caveats worth carrying

* Results were recorded under two different clock start points. The *comparable* columns correct for it; [Measurement validity](#measurement-validity) explains which conclusions are affected (few) and which are not (most).
* The WiFi tables cover only three methods — Arrow Flight, Arrow IPC and gRPC have never been run on WiFi — so WiFi rankings are not comparable to the Ethernet ones.
* BabyROS needs Python 3.11–3.12 and glibc ≥ 2.28, which **rules out the Jetson Nano used here** without a container — see [babyros/README.md](babyros/README.md).

---

## Measurement validity

Timing a message needs a clear start point. Three were used while this study was built, so
every figure in this README is put on **one shared basis**: the clock starts *before* the
random test data is created, which is how most runs were recorded. All data is kept as
originally recorded — the differences are known constants, so they are added back rather than
re-measured.

| Group | Clock started | Runs | Put on the shared basis by |
| :--- | :--- | ---: | :--- |
| **A** | before the data is created | 24 | nothing — this *is* the shared basis |
| **B** | after packing is finished | 2 | **+0.500s** (0.376 creation + 0.124 packing) |
| **C** | after creating, before packing | 11 | **+0.376s** one block, **+0.232s** four blocks |

Group B is Arrow Flight's single-block runs. Group C is BabyROS everywhere, plus the
four-block Arrow Flight and Arrow IPC runs. Every script now starts its clock at the group C
point; the older runs predate that being made uniform.

### What this changes, and what it does not

**Unchanged — everything inside group A moved together:**

* UInt8MultiArray beats String everywhere, by the same margins.
* ROS 2 slows ~70% on the Jetson over a cable, and 88–125% over WiFi.
* Every WiFi conclusion, including UInt8MultiArray winning the four-block test.

**Changed — one ranking:**

Arrow Flight and Arrow IPC were erring in opposite directions. Arrow Flight's clock started
~0.124s **late**; Arrow IPC's included the full ~0.376s of data creation. That put an
artificial half-second between them:

| One block, X86 → X86 | as recorded | shared basis |
| :--- | ---: | ---: |
| Arrow Flight | 1.3901s | 1.8901s |
| Arrow IPC | 1.6057s | **1.6057s** |

Arrow Flight looked fastest and is not. The four-block test, where no such distortion exists,
puts Arrow IPC first independently — so two different payloads agree.

### Reading the numbers

Because the shared basis includes data creation, every figure is ~0.2–0.4s larger than pure
send time. That constant is the same for all methods, so **differences and rankings are
unaffected** — subtract it if you want transmission time alone. Throughput figures quoted in
MB/s already exclude it.

### Still worth collecting

| What | Runs | Why |
| :--- | ---: | :--- |
| `grpc_string_list_numpy_array`, both Ethernet pairs | 2 | Never measured — the only genuinely empty cells |
| Arrow Flight / Arrow IPC / gRPC on WiFi | 6 | No non-ROS method has run on WiFi, so those tables compare three methods, not six |

One caveat no adjustment fixes: latency is the receiver's clock minus the sender's clock, so
if the two machines' clocks drift apart every cross-machine figure carries a fixed offset. It
cancels out when comparing methods on the same pair, so rankings hold — but check
`timedatectl` on both machines before quoting absolute seconds.

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
    ├── {wifi,ethernet}/plots_babyros/     ← BabyROS vs ROS2, single array
    ├── ethernet/plots_list_non_ros/   ← Arrow IPC vs Flight vs BabyROS, list
    └── {wifi,ethernet}/plots_babyros_2nd/ ← BabyROS vs ROS2, list of arrays
```
