import zenoh
import json
from babyros.node import Subscriber, SessionManager
import time
import csv
import os
import argparse
import threading


def configure_session(listen=None, connect=None, block_wait_sec=60.0):
    """Build and install the Zenoh session config for this node.

    Always applied, not only when endpoints are given: the transport tuning
    below matters on every link.

    Built directly rather than via babyros.configure(), which maps --listen to
    'listen/endpoints/peer' — a key eclipse-zenoh 1.10 rejects as unknown. The
    two transport values mirror babyros.configure()'s own defaults and matter
    for large payloads.
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
    parser = argparse.ArgumentParser(description='BabyROS List-of-Arrays Subscriber')
    parser.add_argument('--folder', type=str, default='same_machine')
    parser.add_argument('--topic', type=str, default='big_topic')
    parser.add_argument('--history', type=str, default='keep_last',
                        choices=['keep_last', 'keep_all'])
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
                ["msg_id", "publish_time", "receive_time", "latency", "type"]
            )

    def callback(msg):
        receive_time = time.time()

        msg_id = msg["msg_id"]
        publish_time = msg["publish_time"]
        arrays = [v for k, v in msg.items() if k.startswith("arr_")]

        latency = receive_time - publish_time

        with open(csv_file, "a", newline="") as f:
            csv.writer(f).writerow(
                [msg_id, publish_time, receive_time, latency, "List[4]BabyROS"]
            )

        print(f"📥 Received #{msg_id} | arrays={len(arrays)} | latency={latency:.4f}s")

    sub = Subscriber(topic=args.topic, callback=callback,
                     history=args.history, depth=args.depth)
    print(f"BabyROS list subscriber listening on topic '{args.topic}'")

    try:
        threading.Event().wait()
    except KeyboardInterrupt:
        pass
    finally:
        sub.delete()


if __name__ == '__main__':
    main()
