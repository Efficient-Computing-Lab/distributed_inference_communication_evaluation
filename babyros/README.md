# BabyROS Benchmark

[BabyROS](https://docs.telekinesis.ai/babyros/introduction.html) is a lightweight pub/sub
framework built on [Zenoh](https://zenoh.io/), from Telekinesis (Apache 2.0). It sits
between the two groups already benchmarked here: it keeps the ROS-style
publisher/subscriber API, but replaces DDS with Zenoh and carries numpy arrays as raw
bytes with an Arrow-style manifest — no message schemas, no IDL, no base64.

Part of the [Large-Data Communication Benchmark](../README.md) — see the main README for
the full comparison, and [`docs/methods.md`](../docs/methods.md) for the method index.

Covers both payload shapes used elsewhere in this repo:

| Directory | Payload |
| :--- | :--- |
| `babyros/` | Single 6125×6125 `float32` array (~150 MB) |
| `babyros_list_numpy_array/` | Four `float32` arrays (~99 MB), matching the ROS2 list experiment |

---

## The technology

[Zenoh](https://zenoh.io/) is an Eclipse Foundation protocol from
ZettaScale that unifies pub/sub, query and storage under one abstraction. Where DDS matches
*topics* between typed endpoints, Zenoh routes on **key expressions** (`big_topic`, with
wildcards) and treats payloads as opaque bytes — no IDL, no type registry, no CDR. Nodes can
run as peers (direct, mesh) or through routers; peers on a subnet find each other by
**multicast scouting**, and explicit `listen`/`connect` endpoints work when multicast does
not. The transport layer runs over TCP, UDP, QUIC, Unix sockets or shared memory, batches
small messages, and — critically for this benchmark — exposes **per-publisher congestion
control**. Zenoh is not exotic in a ROS context: `rmw_zenoh` is now an official ROS 2
middleware, so this is roughly "ROS 2 with the DDS layer swapped out".

[BabyROS](https://docs.telekinesis.ai/babyros/introduction.html) (Telekinesis, Apache 2.0) is
a small pure-Python framework on top of it that keeps the ROS shape —
`Publisher(topic=...)`, `Subscriber(topic=..., callback=...)`, `history`/`depth` QoS — while
carrying numpy arrays natively. `pub.publish({"msg_id": ..., "publish_time": ..., "data":
arr})` sends the array bytes raw with an **Arrow-style JSON manifest (NDAR/NDDC)** describing
dtype and shape. No header packing, no base64, and `compression=None` keeps the 150 MB
uncompressed on the wire — the same deal Arrow gets, reached from the other direction.

---

## Install

BabyROS requires **Python ≥3.11, <3.13**. This machine's default is 3.13, so it needs a
separate interpreter:

```bash
python3.12 -m venv ~/venvs/babyros
~/venvs/babyros/bin/pip install babyros
```

Dependencies are `eclipse-zenoh`, `loguru`, `numpy` — no ROS, no system packages, no
workspace build.

### On ARM / Jetson

`babyros` itself is a pure-Python wheel (`py3-none-any`), and `eclipse-zenoh` 1.9.0
publishes an `aarch64` wheel — so ARM is supported in principle. Two constraints decide
whether it works on a given board:

| Requirement | Why |
| :--- | :--- |
| **glibc ≥ 2.28** | The only aarch64 zenoh wheel is `manylinux_2_28`. The `manylinux2014` (glibc 2.17) wheel exists only for the ancient `0.10.0rc0`, whose API BabyROS does not use. |
| **Python 3.11 or 3.12** | Hard bound in the package metadata. |

Check on the device with `ldd --version` and `python3 --version`.

The **Jetson Nano (Cortex-A57)** used elsewhere in this repo runs JetPack 4.x /
Ubuntu 18.04 — glibc 2.27 and Python 3.6. It fails **both** requirements, so BabyROS
cannot be pip-installed on it directly. Options:

1. **Container** (recommended) — run the subscriber in an `ubuntu:22.04`+ image with
   Python 3.12. glibc comes from the image; the host kernel is fine, and `--network host`
   keeps Zenoh's transport unchanged.
2. **Newer board** — Orin-class JetPack 6 (Ubuntu 22.04, glibc 2.35) clears the glibc bar;
   Python 3.10 is still too old, so add 3.12 via deadsnakes or conda.

---

## Running

Start the **subscriber first**, then the publisher. Run from inside the method directory so
`--folder` reproduces the results tree, and use the venv's interpreter on both machines.
Collect ~100 messages (5 s apart → ~9 min), then `Ctrl-C` both sides.

Same machine, two terminals:

```bash
cd babyros                                    # or: babyros_list_numpy_array
~/venvs/babyros/bin/python subscriber.py --folder same_machine
~/venvs/babyros/bin/python publisher.py  --folder same_machine
```

Across machines, Zenoh's multicast scouting usually finds peers on the same subnet, so the
same commands work with only the folder changed:

```bash
cd babyros
~/venvs/babyros/bin/python subscriber.py --folder ethernet/x86_machines   # subscriber host
~/venvs/babyros/bin/python publisher.py  --folder ethernet/x86_machines   # publisher host
```

If discovery fails (different subnets, multicast blocked), set endpoints explicitly:

```bash
# subscriber host (e.g. 147.102.19.67)
~/venvs/babyros/bin/python subscriber.py --folder ethernet/x86_machines \
    --listen tcp/0.0.0.0:7447

# publisher host
~/venvs/babyros/bin/python publisher.py  --folder ethernet/x86_machines \
    --connect tcp/147.102.19.67:7447
```

Use `ethernet/diff_machines` for the Jetson Nano configuration (see the ARM section above —
it needs a container). Both sides must agree on `--topic` if you change it from `big_topic`;
run the two payload shapes on **different** topics if running them concurrently.

Output matches the rest of the repo: `publisher_log.csv` and `subscriber_log.csv` under
`<folder>/`, with the same columns as the corresponding ROS2 experiment
(`latency_sec`/`message_type` for the single array, `latency`/`type` for the list).

### Subscriber options

| Flag | Default | Purpose |
| :--- | :--- | :--- |
| `--history` | `keep_last` | `keep_all` queues instead of dropping stale messages |
| `--depth` | `1` | Queue depth — raise this if sent/received counts diverge |

### Plots

Generated by the two analysis scripts into:

| Output | Comparison |
| :--- | :--- |
| `analysis/ethernet/plots_babyros/{x86_machines,diff_machines}/` | single array, Ethernet |
| `analysis/wifi/plots_babyros/{x86_machines,diff_machines}/` | single array, WiFi |
| `analysis/ethernet/plots_babyros_2nd/{x86_machines,diff_machines}/` | list of arrays, Ethernet |
| `analysis/wifi/plots_babyros_2nd/{x86_machines,diff_machines}/` | list of arrays, WiFi |

```bash
cd analysis
python3 plot_analysis.py            # WiFi
python3 plot_analysis_ethernet.py   # Ethernet
```

Each folder gets `latency_boxplot`, `latency_cdf`, `latency_histogram` and
`latency_vs_msg_id`, comparing BabyROS against UInt8MultiArray and String (Base64).

---

## Results

All measured numbers are reported in the [main README's results table](../README.md#results).
Plots: [`analysis/`](../analysis/); per-experiment detail:
[README_ethernet.md](../README_ethernet.md).

---

## Resolved: the silent message-drop bug

Earlier runs of this benchmark lost ~80% of messages, and cross-machine runs delivered
nothing at all. The cause was in BabyROS itself, not the benchmark.

`babyros/node.py` declares its Zenoh publisher with no congestion-control setting:

```python
self._pub = self._session.declare_publisher(self._topic)
```

Zenoh's default is `CongestionControl.DROP`. A 150 MB payload overflows the transmit queue
long before the transfer completes, so Zenoh **silently discards the message** — `put()`
still returns cleanly and the publisher logs a successful send.

`publisher.py` now re-declares the publisher with `CongestionControl.BLOCK`, so it waits
for queue space instead of discarding. Delivery went from ~20% to 100%. Pass `--allow-drop`
to reproduce the original behaviour.

A second setting matters on slow links: `wait_before_close` is how long a blocking
publisher may wait before Zenoh **closes the transport session**. Stock Zenoh's default is
below the ~8.4 s a 150 MB payload needs over WiFi, which tore the session down mid-run;
`configure_session()` raises it to 60 s, matching what `rmw_zenoh` does for the same
reason. Override with `--block-wait`.

Delivery is still worth checking on any new run:

```bash
wc -l <folder>/publisher_log.csv <folder>/subscriber_log.csv
```

A publisher count higher than the subscriber count usually just means the publisher
outlived the subscriber at shutdown.
