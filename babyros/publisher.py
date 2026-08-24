import zenoh
import json
from babyros.node import Publisher, SessionManager
import numpy as np
import time
import csv
import os
import argparse


DIM = 6125
INTERVAL_SEC = 5.0


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
    parser = argparse.ArgumentParser(description='BabyROS Big Data Publisher')
    parser.add_argument('--folder', type=str, default='same_machine',
                        help='Folder name to save the CSV logs')
    parser.add_argument('--topic', type=str, default='big_topic',
                        help='BabyROS topic name (must not start with "/")')
    parser.add_argument('--listen', type=str, default=None,
                        help='Zenoh endpoint to listen on, e.g. tcp/0.0.0.0:7447')
    parser.add_argument('--connect', type=str, default=None,
                        help='Zenoh endpoint of the peer, e.g. tcp/147.102.19.67:7447')
    args = parser.parse_args()

    configure_session(args.listen, args.connect)

    os.makedirs(args.folder, exist_ok=True)
    csv_file = os.path.join(args.folder, "publisher_log.csv")

    if not os.path.exists(csv_file):
        with open(csv_file, "w", newline="") as f:
            csv.writer(f).writerow(["msg_id", "publish_time", "message_type"])

    # compression=None is explicit, not defensive: BabyROS always sends numpy
    # NDAR/NDDC payloads uncompressed regardless of this setting (the codec only
    # applies to telekinesis-datatypes). Setting it None documents that the
    # 150 MB goes on the wire raw, like the Arrow and raw-TCP benchmarks.
    pub = Publisher(topic=args.topic, compression=None)
    print(f"BabyROS publisher on topic '{args.topic}'")

    msg_id = 0
    try:
        while True:
            msg_id += 1

            arr = np.random.rand(DIM, DIM).astype(np.float32)
            publish_time = time.time()

            # NDDC path: msg_id/publish_time ride in the JSON manifest, the array
            # bytes stay raw in the payload — no header packing, no base64.
            pub.publish({
                "msg_id": msg_id,
                "publish_time": publish_time,
                "data": arr,
            })

            with open(csv_file, "a", newline="") as f:
                csv.writer(f).writerow([msg_id, publish_time, "BabyROS"])

            print(f"🚀 Sent msg #{msg_id}")
            time.sleep(INTERVAL_SEC)

    except KeyboardInterrupt:
        pass
    finally:
        pub.delete()


if __name__ == '__main__':
    main()
