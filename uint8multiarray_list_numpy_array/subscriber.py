import rclpy
from rclpy.node import Node
from std_msgs.msg import UInt8MultiArray
import numpy as np
import time
import struct
import csv
import os
import argparse
import sys


class ListSubscriberUInt8(Node):
    def __init__(self, folder_path):
        super().__init__('list_subscriber_uint8')
        self.sub = self.create_subscription(UInt8MultiArray, 'big_topic', self.callback, 10)

        self.shapes = [
            (1, 120, 160, 5, 64),
            (1, 120, 160, 5, 64, 3),
            (1, 120, 160, 6),
            (1, 120, 160)
        ]

        os.makedirs(folder_path, exist_ok=True)
        self.csv_file = os.path.join(folder_path, "subscriber_log.csv")

        if not os.path.exists(self.csv_file):
            with open(self.csv_file, "w", newline="") as f:
                csv.writer(f).writerow(["msg_id", "publish_time", "receive_time", "latency", "type"])

    def callback(self, msg):
        receive_time = time.time()

        binary_payload = bytes(msg.data)

        header_size = struct.calcsize('=Id4I')
        msg_id, publish_time, *lengths = struct.unpack_from('=Id4I', binary_payload, 0)

        offset = header_size
        arrays = []

        for i, length in enumerate(lengths):
            arr_bytes = binary_payload[offset:offset + length]
            arr = np.frombuffer(arr_bytes, dtype=np.float32).reshape(self.shapes[i])
            arrays.append(arr)
            offset += length

        latency = receive_time - publish_time

        with open(self.csv_file, "a", newline="") as f:
            csv.writer(f).writerow([msg_id, publish_time, receive_time, latency, "List[4]UInt8MultiArray"])

        self.get_logger().info(
            f"📥 Received UInt8MultiArray #{msg_id} | arrays={len(arrays)} | latency={latency:.4f}s"
        )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--folder', type=str, default='multi_array_uint8')
    args, _ = parser.parse_known_args()

    rclpy.init(args=sys.argv)
    node = ListSubscriberUInt8(args.folder)

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass

    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()