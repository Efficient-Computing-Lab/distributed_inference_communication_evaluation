import grpc
import numpy as np
import time
import csv
import os
import argparse

import string_comm_list_pb2
import string_comm_list_pb2_grpc


SHAPES = [
    (1, 120, 160, 5, 64),
    (1, 120, 160, 5, 64, 3),
    (1, 120, 160, 6),
    (1, 120, 160)
]

MAX_MSG = 512 * 1024 * 1024


def main():
    parser = argparse.ArgumentParser(description='gRPC List-of-Arrays Client')
    parser.add_argument('--folder', type=str, default='same_machine',
                        help='Folder to save client CSV log')
    parser.add_argument('--host', type=str, default='localhost', help='Server host')
    parser.add_argument('--port', type=str, default='50051', help='gRPC port')
    args = parser.parse_args()

    os.makedirs(args.folder, exist_ok=True)
    csv_file = os.path.join(args.folder, "client_log.csv")
    if not os.path.exists(csv_file):
        with open(csv_file, "w", newline="") as f:
            csv.writer(f).writerow(
                ["msg_id", "publish_time", "receive_time", "latency", "type"]
            )

    options = [
        ('grpc.max_send_message_length', MAX_MSG),
        ('grpc.max_receive_message_length', MAX_MSG),
    ]
    channel = grpc.insecure_channel(f'{args.host}:{args.port}', options=options)
    stub = string_comm_list_pb2_grpc.DataStreamStub(channel)
    print(f"Connected to gRPC server at {args.host}:{args.port}")

    try:
        for msg in stub.Stream(string_comm_list_pb2.StreamRequest()):
            receive_time = time.time()

            arrays = [
                np.frombuffer(buf, dtype=np.float32).reshape(shape)
                for buf, shape in zip(msg.payloads, SHAPES)
            ]

            latency = receive_time - msg.publish_time

            with open(csv_file, "a", newline="") as f:
                csv.writer(f).writerow(
                    [msg.msg_id, msg.publish_time, receive_time, latency,
                     "List[4]bytes(protobuf)"]
                )

            print(f"Received #{msg.msg_id} | arrays={len(arrays)} | "
                  f"Latency: {latency:.4f}s")
    except KeyboardInterrupt:
        pass
    finally:
        channel.close()


if __name__ == '__main__':
    main()
