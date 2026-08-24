"""Connectivity checker for the BabyROS benchmarks.

Opens a Zenoh session with the same configuration the benchmark scripts use and
reports whether this device can see the other one. Run it on BOTH machines with
the same flags you pass to publisher.py / subscriber.py.

    # subscriber side
    python net_check.py --listen tcp/0.0.0.0:7447

    # publisher side
    python net_check.py --connect tcp/<SUBSCRIBER-IP>:7447

"peers: 1" on both sides means the link is up and the benchmark should work.
"peers: 0" means they never connected — the transport is the problem, not the
benchmark.
"""

import zenoh
import json
import time
import argparse


def main():
    parser = argparse.ArgumentParser(description='BabyROS connectivity checker')
    parser.add_argument('--listen', type=str, default=None,
                        help='Endpoint to listen on, e.g. tcp/0.0.0.0:7447')
    parser.add_argument('--connect', type=str, default=None,
                        help='Endpoint of the peer, e.g. tcp/147.102.19.151:7447')
    parser.add_argument('--debug', action='store_true',
                        help='Enable Zenoh debug logging (babyros never turns it on)')
    args = parser.parse_args()

    if args.debug:
        zenoh.init_log_from_env_or("debug")

    cfg = zenoh.Config()
    if args.listen:
        cfg.insert_json5("listen/endpoints", json.dumps([args.listen]))
    if args.connect:
        cfg.insert_json5("connect/endpoints", json.dumps([args.connect]))
    cfg.insert_json5("transport/link/tx/batch_size", "1048576")
    cfg.insert_json5("transport/link/rx/buffer_size", "209715200")

    session = zenoh.open(cfg)
    print(f"session open — my zid: {session.info.zid()}", flush=True)
    if args.listen:
        print(f"listening on : {args.listen}", flush=True)
    if args.connect:
        print(f"connecting to: {args.connect}", flush=True)
    print("\nwatching for peers (Ctrl-C to stop)\n", flush=True)

    try:
        while True:
            peers = list(session.info.peers_zid())
            links = list(session.info.links())
            status = "LINK UP" if peers else "no peer yet"
            print(f"[{time.strftime('%H:%M:%S')}] {status} | "
                  f"peers: {len(peers)} | links: {len(links)}", flush=True)
            for p in peers:
                print(f"    peer zid: {p}", flush=True)
            time.sleep(2.0)
    except KeyboardInterrupt:
        pass
    finally:
        session.close()


if __name__ == '__main__':
    main()
