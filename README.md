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

| Configuration | Network | UInt8MultiArray | String (Base64) | Winner |
| :--- | :--- | :--- | :--- | :--- |
| Same machine (X86) | — | **0.8447s** | 1.3001s | Binary ~35% faster |
| X86 → Jetson Nano | WiFi | **16.3764s** | 24.8816s | Binary ~34% faster |
| X86 → X86 | WiFi | **8.6934s** | 11.0463s | Binary ~21% faster |
| X86 → Jetson Nano | Ethernet | **3.5886s** | 5.0823s | Binary ~29% faster |
| X86 → X86 | Ethernet | **2.1086s** | 2.9777s | Binary ~29% faster |

**Binary wins in every configuration.** The margin is consistent (~21–35%) regardless of network medium or hardware, because the 33% payload reduction from avoiding Base64 is always a decisive advantage once a network is involved.

---

### List of numpy arrays (~150 MB)

| Configuration | Network | UInt8MultiArray | String (Base64) | Winner |
| :--- | :--- | :--- | :--- | :--- |
| Same machine (X86) | — | 2.4251s | **1.2436s** | String ~49% faster |
| X86 → Jetson Nano | WiFi | **12.9736s** | 18.7159s | Binary ~31% faster |
| X86 → X86 | WiFi | **8.3911s** | 10.5983s | Binary ~21% faster |
| X86 → Jetson Nano | Ethernet | 4.1493s | **3.3067s** | String ~20% faster |
| X86 → X86 | Ethernet | 3.2343s | **2.0153s** | String ~38% faster |

**The winner depends on network speed.** When the link is fast enough (same machine or Ethernet), the constant packing overhead of assembling multiple array chunks into a single flat UInt8MultiArray message (~1.2s) dominates, and String wins. When the network is slower (WiFi cross-machine), the 33% payload reduction of Binary overcomes the packing cost and Binary wins. The crossover point sits between WiFi and Ethernet bandwidth for this payload size.

---

### Non-ROS alternatives (Ethernet only, 150 MB single array)

Transfer speed in MB/s is computed as `payload_bytes / transfer_time`. The network ceiling is the iperf3 baseline for each method's transport: **118 MB/s (TCP)** for Arrow-based and gRPC methods, **120 MB/s (UDP)** for ROS2/DDS methods (FastDDS uses UDP by default).

| Method | Transport | X86 → X86 | MB/s | X86 → Jetson Nano | MB/s |
| :--- | :--- | :--- | :--- | :--- | :--- |
| Network ceiling | TCP | — | **118 MB/s** | — | **118 MB/s** |
| Network ceiling | UDP | — | **120 MB/s** | — | **120 MB/s** |
| **Arrow Flight (gRPC)** | TCP | **1.3901s** | **108 MB/s** | **1.4472s** | **104 MB/s** |
| **Arrow IPC + TCP** | TCP | 1.6057s | 93 MB/s | 1.6648s | 90 MB/s |
| **gRPC String (bytes)** | TCP | 2.1671s | 69 MB/s | 2.2333s | 67 MB/s |
| ROS2 UInt8MultiArray *(reference)* | UDP | 2.1086s | 71 MB/s | 3.5886s | 42 MB/s |
| ROS2 String (Base64) *(reference)* | UDP | 2.9777s | 67 MB/s | 5.0823s | 39 MB/s |

**Arrow Flight moves data at 104–108 MB/s, just 10–14 MB/s short of what the raw link can carry** — the gap is pure protocol overhead (gRPC/HTTP2 framing + Arrow serialization). ROS2 on X86 reaches 67–71 MB/s (~60% of the link), and on the Jetson Nano drops to 39–42 MB/s (~33%), because DDS middleware degrades disproportionately on constrained ARM hardware while TCP/gRPC connections are largely unaffected.

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

| Use case | Recommendation |
| :--- | :--- |
| Single large tensor, any network | **UInt8MultiArray** — consistently 21–35% faster, lower jitter |
| List of tensors, Ethernet link | **String (Base64)** — packing overhead of Binary dominates on fast links |
| List of tensors, WiFi / constrained link | **UInt8MultiArray** — payload size reduction matters more than packing cost |
| List of tensors, constrained receiver (Jetson) | Monitor empirically; Binary advantage narrows on Ethernet but returns on WiFi |
| Minimum latency, no ROS required | **Arrow Flight (gRPC)** — fastest overall, ~34–60% lower than ROS2 Binary |
| Non-ROS, no gRPC dependency | **Arrow IPC + TCP** — nearly identical to Arrow Flight, simpler stack |
| Staying within ROS 2 ecosystem | **UInt8MultiArray** — best ROS2 option at every network tier |

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
│
└── analysis/
    ├── plot_analysis.py               ← generates WiFi plots
    ├── plot_analysis_ethernet.py      ← generates Ethernet plots
    ├── wifi/plots/                    ← single array WiFi plots
    ├── wifi/plots_2nd/                ← list of arrays WiFi plots
    ├── ethernet/plots/                ← single array Ethernet plots
    ├── ethernet/plots_2nd/            ← list of arrays Ethernet plots
    └── ethernet/plots_non_ros/        ← non-ROS Ethernet plots
```
