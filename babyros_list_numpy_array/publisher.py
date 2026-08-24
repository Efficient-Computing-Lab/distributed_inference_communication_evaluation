import zenoh
import json
from babyros.node import Publisher, SessionManager
import numpy as np
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


SHAPES = [
    (1, 120, 160, 5, 64),
    (1, 120, 160, 5, 64, 3),
    (1, 120, 160, 6),
    (1, 120, 160)
]


def main():
    parser = argparse.ArgumentParser(description='BabyROS List-of-Arrays Publisher')
    parser.add_argument('--folder', type=str, default='same_machine')
    parser.add_argument('--topic', type=str, default='big_topic')
    parser.add_argument('--allow-drop', action='store_true',
                        help="Keep BabyROS's default DROP congestion control. "
                             "Only for reproducing the message loss — normal "
                             "runs should not set this")
    parser.add_argument('--block-wait', type=float, default=60.0,
                        help='Seconds a BLOCK publisher may wait for queue space '
                             'before Zenoh closes the transport. Raise on very '
                             'slow links')
    parser.add_argument('--listen', type=str, default=None,
                        help='Zenoh endpoint to listen on, e.g. tcp/0.0.0.0:7447')
    parser.add_argument('--connect', type=str, default=None,
                        help='Zenoh endpoint of the peer, e.g. tcp/147.102.19.67:7447')
    args = parser.parse_args()

    configure_session(args.listen, args.connect, args.block_wait)

    os.makedirs(args.folder, exist_ok=True)
    csv_file = os.path.join(args.folder, "publisher_log.csv")

    if not os.path.exists(csv_file):
        with open(csv_file, "w", newline="") as f:
            csv.writer(f).writerow(["msg_id", "publish_time", "message_type"])

    pub = Publisher(topic=args.topic, compression=None)

    # BabyROS declares its Zenoh publisher without congestion_control, so the
    # default DROP applies and large payloads are silently discarded when the
    # tx queue fills. Re-declare with BLOCK so the publisher waits instead.
    if not args.allow_drop:
        pub._pub.undeclare()
        pub._pub = SessionManager.get_session().declare_publisher(
            args.topic, congestion_control=zenoh.CongestionControl.BLOCK
        )

    mode = "DROP (default)" if args.allow_drop else "BLOCK"
    print(f"BabyROS list publisher on topic '{args.topic}' | congestion control: {mode}")

    msg_id = 0
    try:
        while True:
            msg_id += 1

            arrays = {f"arr_{i}": np.random.rand(*s).astype(np.float32)
                      for i, s in enumerate(SHAPES)}
            publish_time = time.time()

            # NDDC packs all four arrays into one payload natively, recording
            # each one's shape/dtype/offset in the manifest. No manual
            # struct header, and no list(bytes) conversion.
            pub.publish({"msg_id": msg_id, "publish_time": publish_time, **arrays})

            with open(csv_file, "a", newline="") as f:
                csv.writer(f).writerow([msg_id, publish_time, "List[4]BabyROS"])

            print(f"🚀 Sent list msg #{msg_id}")
            time.sleep(INTERVAL_SEC)

    except KeyboardInterrupt:
        pass
    finally:
        pub.delete()


if __name__ == '__main__':
    main()
