import socket
import threading
import pyarrow as pa
import numpy as np
import time
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

# One column per array, plus the two metadata columns the single-array
# benchmark already uses.
SCHEMA = pa.schema(
    [pa.field(f'arr_{i}', pa.large_binary()) for i in range(len(SHAPES))]
    + [pa.field('msg_id', pa.uint32()), pa.field('publish_time', pa.float64())]
)


def handle_client(conn, addr, csv_file):
    print(f"Client connected: {addr}")
    msg_id = 0
    try:
        # Large socket send buffer to avoid stalling on big payloads
        conn.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 256 * 1024 * 1024)
        conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)

        f = conn.makefile('wb')
        writer = pa.ipc.new_stream(f, SCHEMA)

        while True:
            msg_id += 1

            arrays = [np.random.rand(*s).astype(np.float32) for s in SHAPES]

            # Stamped after data generation so latency measures the method
            # (Arrow serialization + TCP transport), not the harness's numpy RNG.
            publish_time = time.time()

            cols = {f'arr_{i}': pa.array([a.tobytes()], type=pa.large_binary())
                    for i, a in enumerate(arrays)}
            cols['msg_id'] = pa.array([msg_id], type=pa.uint32())
            cols['publish_time'] = pa.array([publish_time], type=pa.float64())

            writer.write_batch(pa.record_batch(cols, schema=SCHEMA))
            f.flush()

            with open(csv_file, 'a', newline='') as cf:
                csv.writer(cf).writerow([msg_id, publish_time, 'List[4]ArrowIPC+TCP'])

            print(f"Sent msg #{msg_id}")
            time.sleep(INTERVAL_SEC)

    except (BrokenPipeError, ConnectionResetError, OSError):
        print(f"Client {addr} disconnected")
    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(description='Arrow IPC List-of-Arrays Server')
    parser.add_argument('--folder', type=str, default='same_machine',
                        help='Folder to save server CSV log')
    parser.add_argument('--host', type=str, default='0.0.0.0',
                        help='Interface to bind')
    parser.add_argument('--port', type=int, default=9000, help='TCP port')
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
        print(f"Arrow IPC list server listening on {args.host}:{args.port}")

        while True:
            conn, addr = srv.accept()
            threading.Thread(target=handle_client, args=(conn, addr, csv_file),
                             daemon=True).start()


if __name__ == '__main__':
    main()
