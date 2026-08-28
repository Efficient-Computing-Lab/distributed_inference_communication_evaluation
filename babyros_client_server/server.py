import zenoh
import json
from babyros.node import Server, SessionManager
import numpy as np
import time
import csv
import os
import argparse
import threading
from collections import deque


DIM = 6125


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
    parser = argparse.ArgumentParser(description='BabyROS Client/Server Data Server')
    parser.add_argument('--folder', type=str, default='same_machine',
                        help='Folder name to save the CSV logs')
    parser.add_argument('--topic', type=str, default='big_topic',
                        help='BabyROS topic name (must not start with "/")')
    parser.add_argument('--listen', type=str, default=None,
                        help='Zenoh endpoint to listen on, e.g. tcp/0.0.0.0:7447')
    parser.add_argument('--connect', type=str, default=None,
                        help='Zenoh endpoint of the peer, e.g. tcp/147.102.19.162:7447')
    args = parser.parse_args()

    configure_session(args.listen, args.connect)

    os.makedirs(args.folder, exist_ok=True)
    csv_file = os.path.join(args.folder, "server_log.csv")

    if not os.path.exists(csv_file):
        with open(csv_file, "w", newline="") as f:
            csv.writer(f).writerow(["msg_id", "publish_time", "message_type"])

    state = {"msg_id": 0}
    pending = deque()          # rows are flushed off the reply path
    lock = threading.Lock()

    def handle_request(request):
        with lock:
            state["msg_id"] += 1
            msg_id = state["msg_id"]

        # Clock starts here, before the test data is created, so latency covers the whole
        # path: making the payload, packing it, and moving it. Every method in this repo
        # uses this same start point so the numbers are directly comparable.
        publish_time = time.time()

        arr = np.random.rand(DIM, DIM).astype(np.float32)

        # Queued rather than written here: a CSV append on the reply path would
        # land between the stamp and the actual send, inflating the latency.
        pending.append([msg_id, publish_time, "BabyROS_ClientServer"])

        return {"msg_id": msg_id, "publish_time": publish_time, "data": arr}

    # compression=None is explicit, not defensive: BabyROS always sends numpy
    # NDAR/NDDC payloads uncompressed regardless of this setting.
    server = Server(topic=args.topic, callback=handle_request, compression=None)
    print(f"BabyROS server ready on topic '{args.topic}' — waiting for requests")

    try:
        while True:
            time.sleep(1.0)
            while pending:
                row = pending.popleft()
                with open(csv_file, "a", newline="") as f:
                    csv.writer(f).writerow(row)
                print(f"🚀 Served msg #{row[0]}")
    except KeyboardInterrupt:
        pass
    finally:
        while pending:
            row = pending.popleft()
            with open(csv_file, "a", newline="") as f:
                csv.writer(f).writerow(row)
        server.delete()


if __name__ == '__main__':
    main()
