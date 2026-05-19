import socket
import threading
import numpy as np
import time
import struct
import csv
import os
import argparse


DIM = 6125
INTERVAL_SEC = 5.0

# Header layout: msg_id (uint32) + publish_time (float64) + nbytes (uint32)
HEADER_FMT = '=IdI'
HEADER_SIZE = struct.calcsize(HEADER_FMT)


def handle_client(conn, addr, csv_file):
    print(f"Client connected: {addr}")
    conn.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 256 * 1024 * 1024)
    conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)

    msg_id = 0
    try:
        while True:
            msg_id += 1
            arr = np.random.rand(DIM, DIM).astype(np.float32)
            publish_time = time.time()

            header = struct.pack(HEADER_FMT, msg_id, publish_time, arr.nbytes)
            conn.sendall(header)
            conn.sendall(memoryview(arr))   # zero-copy: sends directly from numpy buffer

            with open(csv_file, 'a', newline='') as f:
                csv.writer(f).writerow([msg_id, publish_time, 'TCP_raw'])

            print(f"Sent msg #{msg_id}")
            time.sleep(INTERVAL_SEC)

    except (BrokenPipeError, ConnectionResetError, OSError):
        print(f"Client {addr} disconnected")
    finally:
        conn.close()


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
    parser = argparse.ArgumentParser(description='Raw TCP Server')
    parser.add_argument('--folder', type=str, default='same_machine')
    parser.add_argument('--host', type=str, default='0.0.0.0')
    parser.add_argument('--port', type=int, default=9000)
    args = parser.parse_args()

    os.makedirs(args.folder, exist_ok=True)
    csv_file = os.path.join(args.folder, 'server_log.csv')
    if not os.path.exists(csv_file):
        with open(csv_file, 'w', newline='') as f:
            csv.writer(f).writerow(['msg_id', 'publish_time', 'message_type'])

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as srv:
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind((args.host, args.port))
        srv.listen(5)
        print(f"Raw TCP server listening on {args.host}:{args.port}")

        while True:
            conn, addr = srv.accept()
            threading.Thread(target=handle_client, args=(conn, addr, csv_file), daemon=True).start()


if __name__ == '__main__':
    main()
