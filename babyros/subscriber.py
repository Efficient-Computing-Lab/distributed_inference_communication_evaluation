import zenoh
import json
from babyros.node import Subscriber, SessionManager
import numpy as np
import time
import csv
import os
import argparse
import threading


DIM = 6125


def configure_session(listen=None, connect=None):
    """Point this node at an explicit peer instead of relying on multicast.

    Built directly rather than via babyros.configure(), which maps --listen to
    'listen/endpoints/peer' — a key eclipse-zenoh 1.10 rejects as unknown. The
    two transport values mirror babyros.configure()'s own defaults and matter
    for 150 MB payloads.
    """
    if not listen and not connect:
        return
    cfg = zenoh.Config()
    if listen:
        cfg.insert_json5("listen/endpoints", json.dumps([listen]))
    if connect:
        cfg.insert_json5("connect/endpoints", json.dumps([connect]))
    cfg.insert_json5("transport/link/tx/batch_size", "1048576")
    cfg.insert_json5("transport/link/rx/buffer_size", "209715200")
    SessionManager.set_session_config(cfg)


def main():
    parser = argparse.ArgumentParser(description='BabyROS Big Data Subscriber')
    parser.add_argument('--folder', type=str, default='same_machine',
                        help='Folder name to save the CSV logs')
    parser.add_argument('--topic', type=str, default='big_topic',
                        help='BabyROS topic name (must not start with "/")')
    parser.add_argument('--history', type=str, default='keep_last',
                        choices=['keep_last', 'keep_all'],
                        help='Queue policy. keep_last drops stale messages so '
                             'latency reflects transfer time')
    parser.add_argument('--depth', type=int, default=1,
                        help='Queue depth. Raise this if the publisher/subscriber '
                             'sent/received counts diverge')
    parser.add_argument('--listen', type=str, default=None,
                        help='Zenoh endpoint to listen on, e.g. tcp/0.0.0.0:7447')
    parser.add_argument('--connect', type=str, default=None,
                        help='Zenoh endpoint of the peer, e.g. tcp/147.102.19.185:7447')
    args = parser.parse_args()

    configure_session(args.listen, args.connect)

    os.makedirs(args.folder, exist_ok=True)
    csv_file = os.path.join(args.folder, "subscriber_log.csv")

    if not os.path.exists(csv_file):
        with open(csv_file, "w", newline="") as f:
            csv.writer(f).writerow(
                ["msg_id", "publish_time", "receive_time", "latency_sec", "message_type"]
            )

    def callback(msg):
        receive_time = time.time()

        msg_id = msg["msg_id"]
        publish_time = msg["publish_time"]
        arr = msg["data"]

        latency = receive_time - publish_time

        with open(csv_file, "a", newline="") as f:
            csv.writer(f).writerow(
                [msg_id, publish_time, receive_time, latency, "BabyROS"]
            )

        print(f"📥 Received #{msg_id} | shape={arr.shape} | Latency: {latency:.4f}s")

    # depth=1 + keep_last drops stale messages, so latency reflects transfer
    # time rather than queue wait — same policy as the Arrow Flight benchmark.
    # Compare received rows against publisher_log.csv: at 150 MB this harness
    # has been seen to deliver only a fraction of what was published.
    sub = Subscriber(topic=args.topic, callback=callback,
                     history=args.history, depth=args.depth)
    print(f"BabyROS subscriber listening on topic '{args.topic}'")

    try:
        threading.Event().wait()
    except KeyboardInterrupt:
        pass
    finally:
        sub.delete()


if __name__ == '__main__':
    main()
