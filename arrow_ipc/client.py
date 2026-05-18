import socket
import pyarrow as pa
import numpy as np
import time
import csv
import os
import argparse


DIM = 6125


def main():
    parser = argparse.ArgumentParser(description='Arrow IPC over TCP Client')
    parser.add_argument('--folder', type=str, default='same_machine',
                        help='Folder to save client CSV log')
    parser.add_argument('--host', type=str, default='localhost',
                        help='Server host')
    parser.add_argument('--port', type=int, default=9000,
                        help='Server TCP port')
    args = parser.parse_args()

    os.makedirs(args.folder, exist_ok=True)
    csv_file = os.path.join(args.folder, 'client_log.csv')
    if not os.path.exists(csv_file):
        with open(csv_file, 'w', newline='') as f:
            csv.writer(f).writerow([
                'msg_id', 'publish_time', 'receive_time', 'latency_sec', 'message_type'
            ])

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        # Large receive buffer to match server send buffer
        s.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 256 * 1024 * 1024)
        s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        s.connect((args.host, args.port))
        print(f"Connected to {args.host}:{args.port}")

        f = s.makefile('rb')
        reader = pa.ipc.open_stream(f)

        try:
            while True:
                batch = reader.read_next_batch()
                receive_time = time.time()

                msg_id = batch.column('msg_id')[0].as_py()
                publish_time = batch.column('publish_time')[0].as_py()
                arr_bytes = batch.column('data')[0].as_py()
                arr = np.frombuffer(arr_bytes, dtype=np.float32).reshape(DIM, DIM)

                latency = receive_time - publish_time

                with open(csv_file, 'a', newline='') as cf:
                    csv.writer(cf).writerow([
                        msg_id, publish_time, receive_time, latency, 'ArrowIPC+TCP'
                    ])

                print(f"Received #{msg_id} | Latency: {latency:.4f}s")

        except pa.lib.ArrowInvalid:
            print("Stream closed by server")
        except KeyboardInterrupt:
            pass


if __name__ == '__main__':
    main()
