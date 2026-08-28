import grpc
import numpy as np
import time
import csv
import os
import argparse
from concurrent import futures

import string_comm_pb2
import string_comm_pb2_grpc

# 6125x6125 float32 ~ 143 MB — raise gRPC limits accordingly
MAX_MSG_BYTES = 200 * 1024 * 1024
INTERVAL_SEC = 5.0
DIM = 6125


class DataStreamServicer(string_comm_pb2_grpc.DataStreamServicer):
    def __init__(self, folder_path):
        self.folder_path = folder_path
        self.msg_id = 0

        os.makedirs(folder_path, exist_ok=True)
        self.csv_file = os.path.join(folder_path, "publisher_log.csv")

        if not os.path.exists(self.csv_file):
            with open(self.csv_file, "w", newline="") as f:
                csv.writer(f).writerow(["msg_id", "publish_time", "message_type"])

    def Stream(self, request, context):
        print("Client connected, starting stream...")
        while context.is_active():
            self.msg_id += 1

            # Clock starts here, before the test data is created, so latency covers the whole
            # path: making the payload, packing it, and moving it. Every method in this repo
            # uses this same start point so the numbers are directly comparable.
            publish_time = time.time()

            arr = np.random.rand(DIM, DIM).astype(np.float32)

            payload = arr.tobytes()

            msg = string_comm_pb2.DataMessage(
                msg_id=self.msg_id,
                publish_time=publish_time,
                payload=payload,
                message_type="bytes(struct+numpy)",
            )
            yield msg

            with open(self.csv_file, "a", newline="") as f:
                csv.writer(f).writerow([self.msg_id, publish_time, "bytes(struct+numpy)"])

            print(f"Sent msg #{self.msg_id}")
            time.sleep(INTERVAL_SEC)


def main():
    parser = argparse.ArgumentParser(description='gRPC Big Data Server (publisher)')
    parser.add_argument('--folder', type=str, default='same_machine',
                        help='Folder name to save CSV logs')
    parser.add_argument('--port', type=str, default='50051',
                        help='Port to listen on')
    args = parser.parse_args()

    server = grpc.server(
        futures.ThreadPoolExecutor(max_workers=4),
        options=[
            ('grpc.max_send_message_length',    MAX_MSG_BYTES),
            ('grpc.max_receive_message_length', MAX_MSG_BYTES),
        ],
    )
    string_comm_pb2_grpc.add_DataStreamServicer_to_server(
        DataStreamServicer(args.folder), server
    )
    server.add_insecure_port(f'[::]:{args.port}')
    server.start()
    print(f"Server listening on port {args.port}, logging to '{args.folder}/'")

    try:
        server.wait_for_termination()
    except KeyboardInterrupt:
        server.stop(0)


if __name__ == '__main__':
    main()
