import pyarrow as pa
import pyarrow.flight as fl
import numpy as np
import time
import struct
import csv
import os
import argparse


INTERVAL_SEC = 5.0

SHAPES = [
    (1, 120, 160, 5, 64),
    (1, 120, 160, 5, 64, 3),
    (1, 120, 160, 6),
    (1, 120, 160)
]

# One column per array — the idiomatic Arrow mapping for this payload, and the
# closest analogue to what BabyROS's NDDC format does. No flattening into a
# single contiguous buffer, so there is no packing tax to pay.
SCHEMA = pa.schema([pa.field(f'arr_{i}', pa.large_binary()) for i in range(len(SHAPES))])


class ListStreamServer(fl.FlightServerBase):
    def __init__(self, location, folder_path, **kwargs):
        super().__init__(location, **kwargs)
        self._msg_id = 0

        os.makedirs(folder_path, exist_ok=True)
        self._csv_file = os.path.join(folder_path, "server_log.csv")
        if not os.path.exists(self._csv_file):
            with open(self._csv_file, "w", newline="") as f:
                csv.writer(f).writerow(["msg_id", "publish_time", "message_type"])

    def do_get(self, context, ticket):
        def generate():
            while True:
                self._msg_id += 1

                arrays = [np.random.rand(*s).astype(np.float32) for s in SHAPES]

                # Stamped after data generation and before Arrow serialization,
                # matching the convention used by the other publishers here.
                # Note this differs from arrow_flight/ (single array), which
                # stamps at yield and so excludes batch construction.
                publish_time = time.time()

                batch = pa.record_batch(
                    [pa.array([a.tobytes()], type=pa.large_binary()) for a in arrays],
                    schema=SCHEMA,
                )
                metadata = struct.pack('=Id', self._msg_id, publish_time)

                with open(self._csv_file, "a", newline="") as f:
                    csv.writer(f).writerow(
                        [self._msg_id, publish_time, "List[4]ArrowFlight"]
                    )

                print(f"Sent msg #{self._msg_id}")
                yield batch, metadata
                time.sleep(INTERVAL_SEC)

        return fl.GeneratorStream(SCHEMA, generate())


def main():
    parser = argparse.ArgumentParser(description='Arrow Flight List-of-Arrays Server')
    parser.add_argument('--folder', type=str, default='same_machine',
                        help='Folder to save server CSV log')
    parser.add_argument('--host', type=str, default='0.0.0.0',
                        help='Interface to bind (use 0.0.0.0 for all)')
    parser.add_argument('--port', type=int, default=8815,
                        help='Port for the Flight server')
    args = parser.parse_args()

    location = fl.Location.for_grpc_tcp(args.host, args.port)
    server = ListStreamServer(location, args.folder)
    print(f"Arrow Flight list server listening on grpc+tcp://{args.host}:{args.port}")

    try:
        server.serve()
    except KeyboardInterrupt:
        server.shutdown()


if __name__ == '__main__':
    main()
