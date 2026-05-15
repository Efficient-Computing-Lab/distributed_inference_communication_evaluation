import grpc
import time
import csv
import os
import argparse

import string_comm_pb2
import string_comm_pb2_grpc

MAX_MSG_BYTES = 200 * 1024 * 1024


def main():
    parser = argparse.ArgumentParser(description='gRPC Big Data Client (subscriber)')
    parser.add_argument('--folder', type=str, default='same_machine',
                        help='Folder name to save CSV logs')
    parser.add_argument('--host', type=str, default='localhost',
                        help='Server host')
    parser.add_argument('--port', type=str, default='50051',
                        help='Server port')
    args = parser.parse_args()

    os.makedirs(args.folder, exist_ok=True)
    csv_file = os.path.join(args.folder, "subscriber_log.csv")

    if not os.path.exists(csv_file):
        with open(csv_file, "w", newline="") as f:
            csv.writer(f).writerow(
                ["msg_id", "publish_time", "receive_time", "latency_sec", "message_type"]
            )

    channel = grpc.insecure_channel(
        f'{args.host}:{args.port}',
        options=[
            ('grpc.max_send_message_length',    MAX_MSG_BYTES),
            ('grpc.max_receive_message_length', MAX_MSG_BYTES),
        ],
    )
    stub = string_comm_pb2_grpc.DataStreamStub(channel)

    print(f"Connecting to {args.host}:{args.port}, logging to '{args.folder}/'")
    try:
        for msg in stub.Stream(string_comm_pb2.StreamRequest()):
            receive_time = time.time()
            latency = receive_time - msg.publish_time

            with open(csv_file, "a", newline="") as f:
                csv.writer(f).writerow(
                    [msg.msg_id, msg.publish_time, receive_time, latency, msg.message_type]
                )

            print(f"Received #{msg.msg_id} | Latency: {latency:.4f}s")
    except KeyboardInterrupt:
        pass
    finally:
        channel.close()


if __name__ == '__main__':
    main()
