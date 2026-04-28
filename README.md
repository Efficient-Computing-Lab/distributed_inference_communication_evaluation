# ROS 2 Latency Benchmark: UInt8MultiArray vs. String Base64

This project benchmarks the performance of two data transmission methods in Ros2 Jazzy version when handling large payloads (**150 MB**). The data represents a `float32` NumPy array. 



**First Experiment Setup:**
* **Payload:** 150 MB (randomly generated `float32` array).
* **Environment:** Publisher and Subscriber running on the same X86 machine.

**Second Experiment Setup:**
* **Payload:** 150 MB (randomly generated `float32` array).
* **Environment:** Publisher runs on X86 machine and Subscriber runs on a Jetson Nano.
* **Network Type:** Local Network 

## First Experiment
We compared **UInt8MultiArray** (Raw Binary) against **String Base64** (Text Encoding). The goal was to measure **Latency**—the total time from message publication to successful receipt and reconstruction.

![Latency Boxplot](analysis/plots/same_machine/latency_boxplot.png)

### The Results at a Glance
| Metric | UInt8MultiArray (Binary) | String (Base64) |
| :--- | :--- | :--- |
| **Payload Size** | 150 MB | 150 MB |
| **Transmission Size** | ~150 MB | ~200 MB (33% overhead) |
| **Average Latency** | **0.8447 seconds** | **1.3001 seconds** |
| **Performance Gain** | **~35% Faster** | - |

---

## Key Findings

### 1. Speed & Efficiency: The "Serialization Tax"
The **UInt8MultiArray** is significantly faster because it uses raw memory casting. By calling `.tobytes()` and `np.frombuffer()`, the system avoids complex data translation. 

The **String (Base64)** method incurs a heavy "Serialization Tax." The CPU must mathematically transform every byte into an ASCII character, increasing the data volume to **200 MB** and adding a constant overhead of roughly **0.45 seconds**.

![Speed & Efficiency](analysis/plots/same_machine/latency_vs_msg_id.png)
*Note: Both methods show a "warm-up" spike for the first few messages before stabilizing.*

### 2. Stability & Jitter
As shown in the distribution plots, the binary method is not only faster but more **predictable**:
- **Binary (Blue):** Highly stable with very low variance (tightly packed histogram).
- **Base64 (Orange):** Exhibits significant **jitter** (latency spikes). This is due to the inconsistent CPU time required to decode large Base64 strings.

![Stability](analysis/plots/same_machine/latency_histogram.png)

---

### Visualization Summary

* **Box Plot:** Demonstrates that the "worst-case" outliers for the binary method are still significantly faster than the "best-case" scenarios for Base64.
* **Histogram:** Displays two distinct, non-overlapping populations. The binary group is localized at the 0.8s mark, while the Base64 group is spread across the 1.3s mark.
* **CDF Plot:** Confirms that **100%** of binary messages are fully processed before the first Base64 message even arrives.

![CDF](analysis/plots/same_machine/latency_cdf.png)

## Second Experiment
We compared **UInt8MultiArray** (Raw Binary) against **String Base64** (Text Encoding). The goal was to measure **Latency**—the total time from message publication to successful receipt and reconstruction.

![Latency Boxplot](analysis/plots/diff_machine/latency_boxplot.png)

### The Results at a Glance
| Metric | UInt8MultiArray (Binary) | String (Base64)        |
| :--- |:-------------------------|:-----------------------|
| **Payload Size** | 150 MB                   | 150 MB                 |
| **Transmission Size** | ~150 MB                  | ~200 MB (33% overhead) |
| **Average Latency** | **16.3764 seconds**      | **24.8816 seconds**    |
| **Performance Gain** | **~34.2% Faster**        | -                      |

---

## Key Findings

### 1. Speed & Efficiency: The "Serialization Tax"
In a multi-machine environment, UInt8MultiArray is the superior transport method because it minimizes the raw data footprint. By utilizing .tobytes() and np.frombuffer(), the system performs a direct memory cast to raw binary, ensuring that only the original 150 MB is pushed to the network interface.

In contrast, the String (Base64) method imposes a massive "Bandwidth Tax." Beyond the CPU overhead of mathematical transformation, the encoding expands the data volume by 33%, forcing the network to handle 200 MB per message. This expansion directly causes the ~8.5-second latency gap observed in the results.

Note: Both methods exhibit an initial "warm-up" spike (visible in the Msg ID plot) as the DDS middleware establishes discovery and allocates network buffers before reaching a stabilized, albeit volatile, state.

![Speed & Efficiency](analysis/plots/diff_machine/latency_vs_msg_id.png)
*Note: Both methods show a "warm-up" spike for the first few messages before stabilizing.*

### 2. Stability & Jitter
The Multi-Machine experiment confirms that the binary method is not only faster but far more predictable under heavy network load.

* UInt8MultiArray (Blue): Demonstrates high consistency. In the histogram, the blue bars form a tight, tall "tower" between 12 and 18 seconds. This indicates that the network can reliably handle the 150 MB binary payload with minimal variance.

* Base64 (Orange): Exhibits extreme jitter and unpredictability. The orange distribution is much wider and shifted significantly to the right (peaking around 25 seconds). Because the 200 MB payload pushes the network to its physical limit, even minor congestion causes massive delays, as seen in the "long tail" of the histogram and the boxplot outliers reaching 48+ seconds.

* The Overlap Zone: The small brownish region where the two shapes meet (roughly between 16 and 20 seconds) represents rare instances where the methods perform similarly. This occurs when a "lucky" String message catches a window of perfect network health, allowing it to match the speed of a "slow" Binary message delayed by a minor collision. However, this is the exception, not the rule; the vast separation of the peaks proves that Binary is systematically superior.

![Stability](analysis/plots/diff_machine/latency_histogram.png)

### Visualization Summary

* **Box Plot:** Highlights the massive performance gap; the "worst-case" outliers for the Binary method (the highest spikes) are still significantly faster than the "average" (median) performance of the Base64 method.

* **Histogram:** Displays two distinct populations with a minimal overlap zone. The Binary group is localized and tall between 12s and 18s, while the Base64 group is spread much wider across the 24s to 28s range, demonstrating higher variance.

* **CDF Plot:** Confirms a "Deterministic vs. Probabilistic" divide. The steep Binary curve shows that 90% of binary messages are fully processed before even the first 20% of Base64 messages arrive, proving far superior reliability for time-critical tasks.

![CDF](analysis/plots/diff_machine/latency_cdf.png)