import pyarrow as pa
import pyarrow.flight as fl
import numpy as np
import time
import struct
import csv
import os
import argparse
import threading
import queue


DIM = 6125
INTERVAL_SEC = 5.0
SCHEMA = pa.schema([pa.field('data', pa.large_binary())])


class DataStreamServer(fl.FlightServerBase):
    def __init__(self, location, folder_path, **kwargs):
        super().__init__(location, **kwargs)
        self._clients = []
        self._clients_lock = threading.Lock()
        self._msg_id = 0

        os.makedirs(folder_path, exist_ok=True)
        self._csv_file = os.path.join(folder_path, "server_log.csv")
        if not os.path.exists(self._csv_file):
            with open(self._csv_file, "w", newline="") as f:
                csv.writer(f).writerow(["msg_id", "publish_time", "dropped_msgs", "message_type"])

        self._gen_thread = threading.Thread(target=self._generate_loop, daemon=True)
        self._gen_thread.start()

    def _generate_loop(self):
        while True:
            self._msg_id += 1
            publish_time = time.time()

            arr = np.random.rand(DIM, DIM).astype(np.float32)

            batch = pa.record_batch(
                [pa.array([arr.tobytes()], type=pa.large_binary())],
                schema=SCHEMA,
            )
            # Per-batch metadata carries msg_id + publish_time (no extra column needed)
            metadata = struct.pack('=Id', self._msg_id, publish_time)

            dropped = 0
            with self._clients_lock:
                for q in self._clients:
                    # Drain stale messages so latency reflects transfer time, not queue wait
                    while not q.empty():
                        try:
                            q.get_nowait()
                            dropped += 1
                        except queue.Empty:
                            break
                    if dropped:
                        print(f"  WARNING: dropped {dropped} stale message(s) — client too slow")
                    q.put((batch, metadata))

            with open(self._csv_file, "a", newline="") as f:
                csv.writer(f).writerow([self._msg_id, publish_time, dropped, "ArrowFlight"])

            print(f"Sent msg #{self._msg_id} to {len(self._clients)} client(s)")
            time.sleep(INTERVAL_SEC)

    def do_get(self, context, ticket):
        q = queue.Queue()
        with self._clients_lock:
            self._clients.append(q)

        def generate():
            try:
                while True:
                    item = q.get()
                    if item is None:
                        return
                    # Drain stale messages, keep only the latest
                    while not q.empty():
                        try:
                            newer = q.get_nowait()
                            if newer is None:
                                return
                            item = newer
                        except queue.Empty:
                            break
                    batch, meta = item
                    msg_id, _ = struct.unpack('=Id', meta)
                    # Stamp actual send time so latency = pure transfer time
                    send_time = time.time()
                    yield batch, struct.pack('=Id', msg_id, send_time)
            finally:
                with self._clients_lock:
                    try:
                        self._clients.remove(q)
                    except ValueError:
                        pass

        return fl.GeneratorStream(SCHEMA, generate())

    def shutdown(self):
        # Unblock all waiting generators before shutting down
        with self._clients_lock:
            for q in self._clients:
                q.put(None)
        super().shutdown()


def main():
    parser = argparse.ArgumentParser(description='Arrow Flight Data Server')
    parser.add_argument('--folder', type=str, default='same_machine',
                        help='Folder to save server CSV log')
    parser.add_argument('--host', type=str, default='0.0.0.0',
                        help='Interface to bind (use 0.0.0.0 for all)')
    parser.add_argument('--port', type=int, default=8815,
                        help='Port for the Flight server')
    args = parser.parse_args()

    location = fl.Location.for_grpc_tcp(args.host, args.port)
    server = DataStreamServer(location, args.folder)
    print(f"Arrow Flight server listening on grpc+tcp://{args.host}:{args.port}")

    try:
        server.serve()
    except KeyboardInterrupt:
        server.shutdown()


if __name__ == '__main__':
    main()
