import socket
import pyarrow as pa
import numpy as np
import time
import csv
import os
import argparse


SHAPES = [
    (1, 120, 160, 5, 64),
    (1, 120, 160, 5, 64, 3),
    (1, 120, 160, 6),
    (1, 120, 160)
]


def main():
    parser = argparse.ArgumentParser(description='Arrow IPC List-of-Arrays Client')
    parser.add_argument('--folder', type=str, default='same_machine',
                        help='Folder to save client CSV log')
    parser.add_argument('--host', type=str, default='localhost',
                        help='Server host')
    parser.add_argument('--port', type=int, default=9000, help='TCP port')
    args = parser.parse_args()

    os.makedirs(args.folder, exist_ok=True)
    csv_file = os.path.join(args.folder, 'client_log.csv')
    if not os.path.exists(csv_file):
        with open(csv_file, 'w', newline='') as f:
            csv.writer(f).writerow(
                ['msg_id', 'publish_time', 'receive_time', 'latency', 'type']
            )

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 256 * 1024 * 1024)
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        sock.connect((args.host, args.port))
        print(f"Connected to Arrow IPC server at {args.host}:{args.port}")

        f = sock.makefile('rb')
        reader = pa.ipc.open_stream(f)

        try:
            for batch in reader:
                receive_time = time.time()

                msg_id = batch.column('msg_id')[0].as_py()
                publish_time = batch.column('publish_time')[0].as_py()

                arrays = [
                    np.frombuffer(
                        batch.column(f'arr_{i}')[0].as_py(), dtype=np.float32
                    ).reshape(shape)
                    for i, shape in enumerate(SHAPES)
                ]

                latency = receive_time - publish_time

                with open(csv_file, 'a', newline='') as cf:
                    csv.writer(cf).writerow(
                        [msg_id, publish_time, receive_time, latency,
                         'List[4]ArrowIPC+TCP']
                    )

                print(f"Received #{msg_id} | arrays={len(arrays)} | "
                      f"Latency: {latency:.4f}s")
        except KeyboardInterrupt:
            pass


if __name__ == '__main__':
    main()
