# ROS 2 & Non-ROS Communication Latency Benchmark

This repository benchmarks the latency of transmitting large **~150 MB `float32`** payloads across a variety of ROS 2 message types and non-ROS transport protocols, over both WiFi and Ethernet, on heterogeneous hardware (X86 and Jetson Nano).

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

Both methods were tested on two payload shapes:
- **Single array:** one 6125×6125 `float32` matrix (~150 MB)
- **List of arrays:** four multi-dimensional `float32` arrays totalling ~150 MB

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

### Single numpy array (150 MB)

| Configuration | Network | UInt8MultiArray | String (Base64) | BabyROS (Zenoh) | Winner |
| :--- | :--- | :--- | :--- | :--- | :--- |
| Same machine (X86) | — | **0.8447s** | 1.3001s | — | Binary ~35% faster |
| X86 → Jetson Nano | WiFi | 16.3764s | 24.8816s | **5.3616s** | BabyROS ~67% faster |
| X86 → X86 | WiFi | 8.6934s | 11.0463s | **6.0422s** | BabyROS ~30% faster |
| X86 → Jetson Nano | Ethernet | 3.5886s | 5.0823s | **1.5842s** | BabyROS ~56% faster |
| X86 → X86 | Ethernet | 2.1086s | 2.9777s | **1.5900s** | BabyROS ~25% faster |

**Between the two ROS 2 methods, Binary wins everywhere** (~21–35%), because avoiding Base64 removes 33% of the payload once a network is involved.

**BabyROS beats both in every cross-machine configuration**, and its margin is widest exactly where ROS 2 struggles most. Its Ethernet latency to the Jetson Nano (1.5842s) is indistinguishable from its latency to another X86 (1.5900s), while both ROS 2 methods slow by ~70% on ARM. DDS middleware cost scales with receiver CPU; Zenoh's lighter stack does not.

---

### List of numpy arrays (~150 MB)

| Configuration | Network | UInt8MultiArray | String (Base64) | BabyROS | Arrow Flight | Arrow IPC | Winner |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| Same machine (X86) | — | 2.4251s | **1.2436s** | — | — | — | String ~49% faster |
| X86 → Jetson Nano | WiFi | **12.9736s** | 18.7159s | not collected | not collected | not collected | Binary ~31% faster |
| X86 → X86 | WiFi | **8.3911s** | 10.5983s | 10.2884s | not collected | not collected | Binary ~23% faster |
| X86 → Jetson Nano | Ethernet | 4.1493s | 3.3067s | 1.1378s | 1.0294s | **0.9968s** | Arrow IPC ~3.2% faster |
| X86 → X86 | Ethernet | 3.2343s | 2.0153s | 1.1397s | 1.0300s | **0.9646s** | Arrow IPC ~6.3% faster |

**Arrow IPC + TCP wins both Ethernet list configurations** — 102.5 MB/s on X86→X86 with a
0.0060s standard deviation, the tightest distribution anywhere in this repository. The
simplest transport wins here: at 98.84 MB the payload is small enough that gRPC/HTTP2
framing overhead stops being amortised, and a raw socket carrying Arrow IPC beats both
Arrow Flight and Zenoh.

All four non-ROS methods on these two rows stamp `publish_time` identically (after data
generation, before serialization), so this is the only strictly like-for-like comparison in
the repository.

> The non-ROS methods were originally benchmarked only on the single-array payload.
> `arrow_flight_list_numpy_array/`, `arrow_ipc_list_numpy_array/` and
> `grpc_string_list_numpy_array/` close that gap. Arrow Flight and Arrow IPC are collected
> for both Ethernet pairs; gRPC and all WiFi cells are still outstanding. Where a cell reads
> *not collected*, the winner shown is the best of the methods that were measured.

**The winner depends on network speed.** When the link is fast enough (same machine or Ethernet), the constant packing overhead of assembling multiple array chunks into a single flat UInt8MultiArray message (~1.2s) dominates, and String wins. When the network is slower (WiFi cross-machine), the 33% payload reduction of Binary overcomes the packing cost and Binary wins. The crossover point sits between WiFi and Ethernet bandwidth for this payload size.

**BabyROS sidesteps the packing tax entirely** — its NDDC wire format carries several arrays natively, each with its own shape and dtype, so nothing is flattened. That wins Ethernet by 43–66%. WiFi X86→X86 is the single configuration in this repository where BabyROS loses: once a ~140 Mbit/s radio is the bottleneck the packing cost stops mattering, and DDS's fragmentation handles the lossy link better.

---

### Non-ROS alternatives (Ethernet only, 150 MB single array)

Transfer speed in MB/s is computed as `payload_bytes / transfer_time`. The network ceiling is the iperf3 baseline for each method's transport: **118 MB/s (TCP)** for Arrow-based and gRPC methods, **120 MB/s (UDP)** for ROS2/DDS methods (FastDDS uses UDP by default).

| Method | Transport | X86 → X86 | MB/s | X86 → Jetson Nano | MB/s |
| :--- | :--- | :--- | :--- | :--- | :--- |
| Network ceiling | TCP | — | **118 MB/s** | — | **118 MB/s** |
| Network ceiling | UDP | — | **120 MB/s** | — | **120 MB/s** |
| **Arrow Flight (gRPC)** | TCP | **1.3901s** | **108 MB/s** | **1.4472s** | **104 MB/s** |
| **BabyROS (Zenoh)** | TCP | 1.5900s | 94 MB/s | **1.5842s** | **95 MB/s** |
| **Arrow IPC + TCP** | TCP | 1.6057s | 93 MB/s | 1.6648s | 90 MB/s |
| **gRPC String (bytes)** | TCP | 2.1671s | 69 MB/s | 2.2333s | 67 MB/s |
| ROS2 UInt8MultiArray *(reference)* | UDP | 2.1086s | 71 MB/s | 3.5886s | 42 MB/s |
| ROS2 String (Base64) *(reference)* | UDP | 2.9777s | 67 MB/s | 5.0823s | 39 MB/s |

**Arrow Flight moves data at 104–108 MB/s, just 10–14 MB/s short of what the raw link can carry** — the gap is pure protocol overhead (gRPC/HTTP2 framing + Arrow serialization). ROS2 on X86 reaches 67–71 MB/s (~60% of the link), and on the Jetson Nano drops to 39–42 MB/s (~33%), because DDS middleware degrades disproportionately on constrained ARM hardware while TCP/gRPC connections are largely unaffected.

**BabyROS is the only method whose throughput does not change with the receiver** — 94 MB/s to an X86 and 95 MB/s to the Jetson Nano. Every other method loses ground on ARM (Arrow Flight 108 → 104, Arrow IPC 93 → 90, ROS2 71 → 42). It ranks second overall on X86 and second on the Jetson, while being the only non-ROS option here that keeps a publisher/subscriber API.

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

*Same-machine results are excluded throughout this section — they measure loopback, not a
network, and nothing here is intended for two processes on one host.*

**Arrow IPC + TCP is the fastest method on Ethernet; on WiFi, nothing non-ROS has been
measured yet.** There is no single best option across all links.

Across the eight cross-machine configurations:

| Method | Configurations won |
| :--- | :--- |
| **Arrow IPC + TCP** | **2 of 8** — both Ethernet list cases |
| **Arrow Flight (gRPC)** | **2 of 8** — both Ethernet single-tensor cases |
| **BabyROS (Zenoh)** | **2 of 8** — both WiFi single-tensor cases |
| UInt8MultiArray | 2 — both WiFi list cases |
| String (Base64) | **0** |

The Ethernet list results are the most trustworthy comparison in the repository: Arrow IPC,
Arrow Flight and BabyROS all stamp `publish_time` identically there, so nothing is
flattered by measurement asymmetry.

| Ethernet, list of arrays | X86 → X86 | X86 → Jetson |
| :--- | ---: | ---: |
| **Arrow IPC + TCP** | **0.9646s** (std 0.0060) | **0.9968s** (std 0.0535) |
| Arrow Flight (gRPC) | 1.0300s (std 0.0094) | 1.0294s (std 0.0134) |
| BabyROS (Zenoh) | 1.1397s (std 0.0094) | 1.1378s (std 0.0121) |

Arrow IPC reaches 102.5 MB/s against a 118 MB/s TCP ceiling — 87% of the link — with the
tightest distribution measured anywhere here. The lesson is that protocol overhead stops
paying for itself as payloads shrink: at 98.84 MB a raw socket carrying Arrow IPC beats
gRPC/HTTP2 framing, reversing the single-array result where Arrow Flight led.

**Caveat on the single-tensor rows.** Arrow Flight's 1.3901s/1.4472s exclude ~0.12–0.18s of
Arrow serialization that every other method includes, so its two wins there are not
like-for-like. On a common basis it lands near BabyROS's 1.5900s.

**BabyROS's two wins are uncontested.** No non-ROS method has been benchmarked on WiFi at
all — the link where BabyROS beats ROS 2 by 30–67%. Until Arrow IPC and Arrow Flight are run
there, "BabyROS is best on WiFi" means only "best of the three methods measured on WiFi".

BabyROS remains the pick when you want a publisher/subscriber API rather than a
request/stream client: both Arrow methods require the receiver to open a stream, and neither
offers topic-based pub/sub.

**Take one of the two exceptions instead when:**

| Condition | Use | Margin over BabyROS |
| :--- | :--- | :--- |
| List of arrays, Ethernet | **Arrow IPC + TCP** | 15% faster |
| Single tensor, Ethernet, pub/sub not required | **Arrow Flight** | 9–13% faster (see caveat) |
| List of arrays over WiFi | **UInt8MultiArray** | 23% faster |

And one hard constraint before choosing it: BabyROS requires Python 3.11–3.12 and
glibc ≥ 2.28, which **rules out a stock Jetson Nano** without a container.

### Start here: what constrains you?

| If this is true… | Use | Why |
| :--- | :--- | :--- |
| You **must** run inside ROS 2 (bags, launch files, introspection) | **UInt8MultiArray**, except a list of arrays on a fast link → **String (Base64)** | Only these two are actual ROS 2 message types |
| You want pub/sub semantics but **not** DDS | **BabyROS (Zenoh)** | Fastest ROS-style API tested; the only method immune to a slow receiver |
| You need raw minimum latency and no pub/sub | **Arrow IPC + TCP** for a list of arrays, **Arrow Flight** for a single tensor | Arrow IPC hits 102.5 MB/s on the list payload with the tightest jitter measured |
| Your receiver is **ARM / constrained** | **BabyROS** or **Arrow Flight** | Both hold ~95–104 MB/s on the Jetson; ROS 2 collapses to 39–42 MB/s |
| Your link is **WiFi or lossy** | **BabyROS** for a single tensor, **UInt8MultiArray** for a list | The only case where the two payload shapes disagree |

### Best option per configuration

Measured winner in each cell, with the runner-up for context.

**Single 150 MB tensor**

| Configuration | Best | Runner-up | Margin |
| :--- | :--- | :--- | :--- |
| X86 → X86, Ethernet | **Arrow Flight** 1.3901s | BabyROS 1.5900s | 13% |
| X86 → Jetson, Ethernet | **Arrow Flight** 1.4472s | BabyROS 1.5842s | 9% |
| X86 → X86, WiFi | **BabyROS** 6.0422s | UInt8MultiArray 8.6934s | 30% |
| X86 → Jetson, WiFi | **BabyROS** 5.3616s | UInt8MultiArray 16.3764s | 67% |

**List of ~99 MB across four arrays**

| Configuration | Best | Runner-up | Margin |
| :--- | :--- | :--- | :--- |
| X86 → X86, Ethernet | **Arrow IPC + TCP** 0.9646s | Arrow Flight 1.0300s | 6.3% |
| X86 → Jetson, Ethernet | **Arrow IPC + TCP** 0.9968s | Arrow Flight 1.0294s | 3.2% |
| X86 → X86, WiFi | **UInt8MultiArray** 8.3911s | BabyROS 10.2884s | 23% |
| X86 → Jetson, WiFi | **UInt8MultiArray** 12.9736s | String 18.7159s | 31% |

*The two WiFi rows have no non-ROS entry — Arrow and gRPC have never been run on WiFi.*

Read down the WiFi rows and the pattern is the whole story: BabyROS takes both single-tensor
cases by 30–67%, and loses both list cases by 23%. Payload shape decides the WiFi winner;
on Ethernet it does not.

### The three rules that explain every result

**1. Base64 costs 33% and never pays for itself over a network.** String does not win a single cross-machine configuration on either payload shape. Its best result is second place on the Ethernet list cases, where it beats `UInt8MultiArray` only because its rival pays a worse penalty (rule 2) — and both still lose to BabyROS by 43–66%.

**2. Flattening a list into one buffer costs a flat ~1.2s.** `UInt8MultiArray` must pack four arrays into one contiguous `uint8` buffer. On Ethernet that constant dominates and it falls behind String; on WiFi the transfer time dwarfs it and Binary comes back to win both list cases. BabyROS avoids the cost entirely — its NDDC format carries several arrays natively, each keeping its own shape and dtype — which is why it beats both ROS 2 methods by 43–66% there — though Arrow IPC and Arrow Flight, which are equally free of it, are faster still.

**3. DDS scales with receiver CPU; Zenoh and TCP do not.** Moving from an X86 to a Jetson Nano costs ROS 2 about 70% (2.11s → 3.59s) but costs BabyROS nothing measurable (1.5900s → 1.5842s) and Arrow Flight ~4%. This is the single largest effect in the dataset, and it decides every edge-hardware recommendation above.

### Caveats worth carrying

* The ROS 2 figures predate the unified timing convention and still include ~0.376s of payload generation. Corrected, UInt8MultiArray on Ethernet X86→X86 is nearer 1.73s — so its gap to BabyROS there is ~8%, not 25%. The larger margins (56%, 67%) survive the correction easily.
* Arrow Flight excludes ~0.12–0.18s of Arrow serialization that BabyROS and Arrow IPC include, so the top three on Ethernet are closer than the table suggests.
* Non-ROS methods were only measured on Ethernet. On WiFi the comparison is ROS 2 versus BabyROS only.
* BabyROS needs Python 3.11–3.12 and glibc ≥ 2.28, which **rules out the Jetson Nano used here** without a container — see [babyros/README.md](babyros/README.md).

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
