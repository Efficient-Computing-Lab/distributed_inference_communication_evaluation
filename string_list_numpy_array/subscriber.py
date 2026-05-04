import rclpy
from rclpy.node import Node
from std_msgs.msg import String
import numpy as np
import time
import base64
import struct
import csv
import os
import argparse
import sys


class ListSubscriberString(Node):
    def __init__(self, folder_path):
        super().__init__('list_subscriber_string')
        self.sub = self.create_subscription(String, 'big_topic', self.callback, 10)
        self.shapes = [(1, 120, 160, 5, 64), (1, 120, 160, 5, 64, 3), (1, 120, 160, 6), (1, 120, 160)]

        if not os.path.exists(folder_path): os.makedirs(folder_path)
        self.csv_file = os.path.join(folder_path, "subscriber_log.csv")
        if not os.path.exists(self.csv_file):
            with open(self.csv_file, "w", newline="") as f:
                csv.writer(f).writerow(["msg_id", "publish_time", "receive_time", "latency", "type"])

    def callback(self, msg):
        receive_time = time.time()

        # 1. Decode Base64 back to binary
        binary_payload = base64.b64decode(msg.data)

        # 2. Unpack header (28 bytes)
        header_size = struct.calcsize('=Id4I')
        header_data = struct.unpack_from('=Id4I', binary_payload, 0)
        msg_id, publish_time = header_data[0], header_data[1]
        lengths = header_data[2:]

        # 3. Slice and Reshape each array
        offset = header_size
        arrays = []
        for i, length in enumerate(lengths):
            arr_bytes = binary_payload[offset: offset + length]
            arr = np.frombuffer(arr_bytes, dtype=np.float32).reshape(self.shapes[i])
            arrays.append(arr)
            offset += length

        latency = receive_time - publish_time
        with open(self.csv_file, "a", newline="") as f:
            csv.writer(f).writerow([msg_id, publish_time, receive_time, latency, "List[4]Base64String"])

        self.get_logger().info(f"📥 Received String #{msg_id} | Arrays: {len(arrays)} | Latency: {latency:.4f}s")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--folder', type=str, default='multi_array_string')
    args, _ = parser.parse_known_args()
    rclpy.init(args=sys.argv)
    node = ListSubscriberString(args.folder)
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()