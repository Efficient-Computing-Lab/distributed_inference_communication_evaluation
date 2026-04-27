# ROS 2 Latency Benchmark: UInt8MultiArray vs. String Base64

This project benchmarks the performance of two data transmission methods in ROS 2 when handling large payloads (**150 MB**). The data represents a `float32` NumPy array. 

**Experiment Setup:**
* **Payload:** 150 MB (randomly generated `float32` array).
* **Environment:** Publisher and Subscriber running on the same machine.


## Comparison Overview
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

## Visualization Summary

* **Box Plot:** Demonstrates that the "worst-case" outliers for the binary method are still significantly faster than the "best-case" scenarios for Base64.
* **Histogram:** Displays two distinct, non-overlapping populations. The binary group is localized at the 0.8s mark, while the Base64 group is spread across the 1.3s mark.
* **CDF Plot:** Confirms that **100%** of binary messages are fully processed before the first Base64 message even arrives.

![CDF](analysis/plots/same_machine/latency_cdf.png)

