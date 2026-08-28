import pyarrow as pa
import pyarrow.flight as fl
import numpy as np
import time
import struct
import csv
import os
import argparse


DIM = 6125
INTERVAL_SEC = 5.0
SCHEMA = pa.schema([pa.field('data', pa.large_binary())])


class DataStreamServer(fl.FlightServerBase):
    def __init__(self, location, folder_path, **kwargs):
        super().__init__(location, **kwargs)
        self._msg_id = 0

        os.makedirs(folder_path, exist_ok=True)
        self._csv_file = os.path.join(folder_path, "server_log.csv")
        if not os.path.exists(self._csv_file):
            with open(self._csv_file, "w", newline="") as f:
                csv.writer(f).writerow(["msg_id", "publish_time", "dropped_msgs", "message_type"])

    def do_get(self, context, ticket):
        # Data is generated inside the client's own stream rather than in a
        # broadcast thread feeding a queue. That is what allows publish_time to
        # be stamped *before* Arrow serialization: with the old design the batch
        # was already built by the time the stream could stamp a send time, so
        # ~0.12s of batch construction fell outside the measurement while every
        # other method here included its own serialization cost.
        def generate():
            while True:
                self._msg_id += 1

                # Clock starts here, before the test data is created, so latency covers the whole
                # path: making the payload, packing it, and moving it. Every method in this repo
                # uses this same start point so the numbers are directly comparable.
                publish_time = time.time()

                arr = np.random.rand(DIM, DIM).astype(np.float32)

                batch = pa.record_batch(
                    [pa.array([arr.tobytes()], type=pa.large_binary())],
                    schema=SCHEMA,
                )
                metadata = struct.pack('=Id', self._msg_id, publish_time)

                # dropped_msgs is retained for schema compatibility with earlier
                # runs; there is no queue in this design, so it is always 0.
                with open(self._csv_file, "a", newline="") as f:
                    csv.writer(f).writerow([self._msg_id, publish_time, 0, "ArrowFlight"])

                print(f"Sent msg #{self._msg_id}")
                yield batch, metadata
                time.sleep(INTERVAL_SEC)

        return fl.GeneratorStream(SCHEMA, generate())


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
