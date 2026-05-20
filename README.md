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

| Method | X86 → X86 | X86 → Jetson Nano |
| :--- | :--- | :--- |
| **Arrow Flight (gRPC)** | **1.3901s** | **1.4472s** |
| **Arrow IPC + TCP** | 1.6057s | 1.6648s |
| **gRPC String (bytes)** | 2.1671s | 2.2333s |
| ROS2 UInt8MultiArray *(reference)* | 2.1086s | 3.5886s |
| ROS2 String (Base64) *(reference)* | 2.9777s | 5.0823s |

Non-ROS methods outperform all ROS 2 methods by bypassing DDS fragmentation and discovery overhead. Arrow Flight is the fastest overall. Notably, on the Jetson Nano the non-ROS advantage nearly doubles (Arrow Flight is ~34% faster than ROS2 Binary on X86, but ~60% faster on Jetson Nano), because DDS middleware degrades disproportionately on constrained ARM hardware while TCP/gRPC connections are largely unaffected.

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
