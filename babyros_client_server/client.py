import zenoh
import json
from babyros.node import Client, SessionManager
import time
import csv
import os
import argparse


INTERVAL_SEC = 5.0


def configure_session(listen=None, connect=None, block_wait_sec=60.0):
    """Build and install the Zenoh session config for this node.

    Always applied, not only when endpoints are given: the transport tuning
    below matters on every link.

    Built directly rather than via babyros.configure(), which maps --listen to
    'listen/endpoints/peer' — a key eclipse-zenoh 1.10 rejects as unknown. The
    two transport values mirror babyros.configure()'s own defaults and matter
    for 150 MB payloads.
    """
    cfg = zenoh.Config()
    if listen:
        cfg.insert_json5("listen/endpoints", json.dumps([listen]))
    if connect:
        cfg.insert_json5("connect/endpoints", json.dumps([connect]))
    cfg.insert_json5("transport/link/tx/batch_size", "1048576")
    cfg.insert_json5("transport/link/rx/buffer_size", "209715200")
    # How long a BLOCK-mode publisher may wait for queue space before Zenoh
    # CLOSES the transport session. Stock Zenoh's default is well under the
    # ~9 s a 150 MB payload needs over WiFi, so the link is torn down mid-run;
    # rmw_zenoh raises this to 60 s for exactly the same reason.
    cfg.insert_json5(
        "transport/link/tx/queue/congestion_control/block/wait_before_close",
        str(int(block_wait_sec * 1_000_000)),
    )
    SessionManager.set_session_config(cfg)


def main():
    parser = argparse.ArgumentParser(description='BabyROS Client/Server Data Client')
    parser.add_argument('--folder', type=str, default='same_machine',
                        help='Folder name to save the CSV logs')
    parser.add_argument('--topic', type=str, default='big_topic',
                        help='BabyROS topic name (must not start with "/")')
    parser.add_argument('--timeout', type=float, default=60.0,
                        help='Seconds to wait for a reply. Zenoh defaults to ~10s, '
                             'which is too short for 150 MB over WiFi or to a Jetson')
    parser.add_argument('--listen', type=str, default=None,
                        help='Zenoh endpoint to listen on, e.g. tcp/0.0.0.0:7447')
    parser.add_argument('--connect', type=str, default=None,
                        help='Zenoh endpoint of the peer, e.g. tcp/147.102.19.67:7447')
    args = parser.parse_args()

    configure_session(args.listen, args.connect)

    os.makedirs(args.folder, exist_ok=True)
    csv_file = os.path.join(args.folder, "client_log.csv")

    if not os.path.exists(csv_file):
        with open(csv_file, "w", newline="") as f:
            # First five columns match the other client/server benchmarks;
            # rtt_sec is extra because it is the metric native to request/reply.
            csv.writer(f).writerow(
                ["msg_id", "publish_time", "receive_time", "latency_sec",
                 "message_type", "rtt_sec"]
            )

    # compression=None is explicit, not defensive: BabyROS always sends numpy
    # NDAR/NDDC payloads uncompressed regardless of this setting.
    client = Client(topic=args.topic, timeout=args.timeout, compression=None)
    print(f"BabyROS client requesting on topic '{args.topic}' every {INTERVAL_SEC}s")

    req_id = 0
    timeouts = 0
    try:
        while True:
            req_id += 1

            request_time = time.time()
            responses = client.request({"req_id": req_id})
            receive_time = time.time()

            if not responses:
                timeouts += 1
                print(f"⚠️  Request #{req_id} returned no reply "
                      f"({timeouts} total) — check the server is running")
                time.sleep(INTERVAL_SEC)
                continue

            msg = responses[0]
            msg_id = msg["msg_id"]
            publish_time = msg["publish_time"]
            arr = msg["data"]

            # latency: server hand-off -> client receipt, comparable to the
            # one-way figures reported by every other method here.
            # rtt: full request -> reply round trip, including the request hop.
            latency = receive_time - publish_time
            rtt = receive_time - request_time

            with open(csv_file, "a", newline="") as f:
                csv.writer(f).writerow(
                    [msg_id, publish_time, receive_time, latency,
                     "BabyROS_ClientServer", rtt]
                )

            print(f"📥 Received #{msg_id} | shape={arr.shape} | "
                  f"Latency: {latency:.4f}s | RTT: {rtt:.4f}s")

            time.sleep(INTERVAL_SEC)

    except KeyboardInterrupt:
        pass
    finally:
        if timeouts:
            print(f"\n{timeouts} request(s) returned no reply.")
        client.delete()


if __name__ == '__main__':
    main()
