import pyarrow.flight as fl
import numpy as np
import time
import struct
import csv
import os
import argparse


DIM = 6125


def main():
    parser = argparse.ArgumentParser(description='Arrow Flight Data Client')
    parser.add_argument('--folder', type=str, default='same_machine',
                        help='Folder to save client CSV log')
    parser.add_argument('--host', type=str, default='localhost',
                        help='Arrow Flight server host')
    parser.add_argument('--port', type=int, default=8815,
                        help='Arrow Flight server port')
    args = parser.parse_args()

    os.makedirs(args.folder, exist_ok=True)
    csv_file = os.path.join(args.folder, "client_log.csv")
    if not os.path.exists(csv_file):
        with open(csv_file, "w", newline="") as f:
            csv.writer(f).writerow([
                "msg_id", "publish_time", "receive_time", "latency_sec", "message_type"
            ])

    client = fl.connect(fl.Location.for_grpc_tcp(args.host, args.port))
    print(f"Connected to Arrow Flight server at {args.host}:{args.port}")

    try:
        reader = client.do_get(fl.Ticket(b'stream'))
        while True:
            chunk = reader.read_chunk()
            receive_time = time.time()

            msg_id, publish_time = struct.unpack('=Id', chunk.app_metadata)

            # Zero-copy reconstruction: frombuffer avoids a data copy
            arr_bytes = chunk.data.column('data')[0].as_py()
            arr = np.frombuffer(arr_bytes, dtype=np.float32).reshape(DIM, DIM)

            latency = receive_time - publish_time

            with open(csv_file, "a", newline="") as f:
                csv.writer(f).writerow([
                    msg_id, publish_time, receive_time, latency, "ArrowFlight"
                ])

            print(f"Received #{msg_id} | Latency: {latency:.4f}s")
    except KeyboardInterrupt:
        pass
    finally:
        client.close()


if __name__ == '__main__':
    main()
