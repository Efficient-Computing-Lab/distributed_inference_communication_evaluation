import grpc
import numpy as np
import time
import csv
import os
import argparse
from concurrent import futures

import string_comm_list_pb2
import string_comm_list_pb2_grpc


INTERVAL_SEC = 5.0

SHAPES = [
    (1, 120, 160, 5, 64),
    (1, 120, 160, 5, 64, 3),
    (1, 120, 160, 6),
    (1, 120, 160)
]

MAX_MSG = 512 * 1024 * 1024


class DataStreamServicer(string_comm_list_pb2_grpc.DataStreamServicer):
    def __init__(self, folder_path):
        os.makedirs(folder_path, exist_ok=True)
        self.csv_file = os.path.join(folder_path, "server_log.csv")
        self.msg_id = 0

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

            arrays = [np.random.rand(*s).astype(np.float32) for s in SHAPES]

            msg = string_comm_list_pb2.DataMessage(
                msg_id=self.msg_id,
                publish_time=publish_time,
                payloads=[a.tobytes() for a in arrays],
                message_type="List[4]bytes(protobuf)",
            )
            yield msg

            with open(self.csv_file, "a", newline="") as f:
                csv.writer(f).writerow(
                    [self.msg_id, publish_time, "List[4]bytes(protobuf)"]
                )

            print(f"Sent msg #{self.msg_id}")
            time.sleep(INTERVAL_SEC)


def main():
    parser = argparse.ArgumentParser(description='gRPC List-of-Arrays Server')
    parser.add_argument('--folder', type=str, default='same_machine',
                        help='Folder to save server CSV log')
    parser.add_argument('--port', type=str, default='50051', help='gRPC port')
    args = parser.parse_args()

    options = [
        ('grpc.max_send_message_length', MAX_MSG),
        ('grpc.max_receive_message_length', MAX_MSG),
    ]
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=4), options=options)
    string_comm_list_pb2_grpc.add_DataStreamServicer_to_server(
        DataStreamServicer(args.folder), server
    )
    server.add_insecure_port(f'[::]:{args.port}')
    server.start()
    print(f"gRPC list server listening on port {args.port}")

    try:
        server.wait_for_termination()
    except KeyboardInterrupt:
        server.stop(0)


if __name__ == '__main__':
    main()
