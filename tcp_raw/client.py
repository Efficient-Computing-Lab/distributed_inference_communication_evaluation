import socket
import numpy as np
import time
import struct
import csv
import os
import argparse


DIM = 6125

HEADER_FMT = '=IdI'
HEADER_SIZE = struct.calcsize(HEADER_FMT)


def recv_exact(sock, n):
    """Read exactly n bytes from socket into a pre-allocated bytearray."""
    buf = bytearray(n)
    view = memoryview(buf)
    received = 0
    while received < n:
        chunk = sock.recv_into(view[received:], n - received)
        if chunk == 0:
            raise ConnectionResetError("Connection closed by server")
        received += chunk
    return buf


def main():
    parser = argparse.ArgumentParser(description='Raw TCP Client')
    parser.add_argument('--folder', type=str, default='same_machine')
    parser.add_argument('--host', type=str, default='localhost')
    parser.add_argument('--port', type=int, default=9000)
    args = parser.parse_args()

    os.makedirs(args.folder, exist_ok=True)
    csv_file = os.path.join(args.folder, 'client_log.csv')
    if not os.path.exists(csv_file):
        with open(csv_file, 'w', newline='') as f:
            csv.writer(f).writerow([
                'msg_id', 'publish_time', 'receive_time', 'latency_sec', 'message_type'
            ])

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 256 * 1024 * 1024)
        s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        s.connect((args.host, args.port))
        print(f"Connected to {args.host}:{args.port}")

        try:
            while True:
                # Receive fixed-size header
                header_buf = recv_exact(s, HEADER_SIZE)
                msg_id, publish_time, nbytes = struct.unpack(HEADER_FMT, header_buf)

                # Receive array directly into a pre-allocated buffer — no copy
                arr_buf = recv_exact(s, nbytes)
                receive_time = time.time()

                arr = np.frombuffer(arr_buf, dtype=np.float32).reshape(DIM, DIM)

                latency = receive_time - publish_time

                with open(csv_file, 'a', newline='') as f:
                    csv.writer(f).writerow([
                        msg_id, publish_time, receive_time, latency, 'TCP_raw'
                    ])

                print(f"Received #{msg_id} | Latency: {latency:.4f}s")

        except (ConnectionResetError, OSError):
            print("Server disconnected")
        except KeyboardInterrupt:
            pass


if __name__ == '__main__':
    main()
