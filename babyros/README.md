# BabyROS Benchmark

[BabyROS](https://docs.telekinesis.ai/babyros/introduction.html) is a lightweight pub/sub
framework built on [Zenoh](https://zenoh.io/), from Telekinesis (Apache 2.0). It sits
between the two groups already benchmarked here: it keeps the ROS-style
publisher/subscriber API, but replaces DDS with Zenoh and carries numpy arrays as raw
bytes with an Arrow-style manifest — no message schemas, no IDL, no base64.

Covers both payload shapes used elsewhere in this repo:

| Directory | Payload |
| :--- | :--- |
| `babyros/` | Single 6125×6125 `float32` array (~150 MB) |
| `babyros_list_numpy_array/` | Four `float32` arrays (~99 MB), matching the ROS2 list experiment |

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

Not yet wired into `analysis/plot_analysis_ethernet.py`; add the CSVs there once collected.

---

## ⚠️ Open issue: message delivery

**Verify delivery ratio before reporting any latency numbers from this benchmark.**

In local validation on this machine, a two-process run at 150 MB published **9 messages
and delivered 2** — consistently every *other* message. The same payload published and
received *within a single process* (shared Zenoh session) delivered 100% at 15/50/150 MB,
so it is specific to the cross-process path, and it is not discovery (a 12 s settle before
the first publish did not help).

This matters because the surviving messages still report a healthy ~0.30 s latency. Taking
that at face value would be survivorship bias: it measures only the transfers that were
not dropped.

The harness makes this checkable — compare row counts:

```bash
wc -l <folder>/publisher_log.csv <folder>/subscriber_log.csv
```

`--history keep_all --depth 10` on the subscriber is the first thing to try. Treat
delivery ratio as a reported metric alongside latency, the way `arrow_flight/server.py`
already logs `dropped_msgs`.
