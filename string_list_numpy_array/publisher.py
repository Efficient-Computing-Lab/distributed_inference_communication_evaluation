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


class ListPublisherString(Node):
    def __init__(self, folder_path):
        super().__init__('list_publisher_string')
        self.pub = self.create_publisher(String, 'big_topic', 10)
        self.timer = self.create_timer(5.0, self.send)
        self.msg_id = 0

        # Specified shapes
        self.shapes = [
            (1, 120, 160, 5, 64),
            (1, 120, 160, 5, 64, 3),
            (1, 120, 160, 6),
            (1, 120, 160)
        ]

        if not os.path.exists(folder_path): os.makedirs(folder_path)
        self.csv_file = os.path.join(folder_path, "publisher_log.csv")
        if not os.path.exists(self.csv_file):
            with open(self.csv_file, "w", newline="") as f:
                csv.writer(f).writerow(["msg_id", "publish_time", "message_type"])

    def send(self):
        self.msg_id += 1
        publish_time = time.time()

        # 1. Convert all arrays to raw bytes
        byte_arrays = [np.random.rand(*s).astype(np.float32).tobytes() for s in self.shapes]
        lengths = [len(b) for b in byte_arrays]

        # 2. Pack Header: ID (I), Time (d), and 4 lengths (4I)
        header = struct.pack('=Id4I', self.msg_id, publish_time, *lengths)

        # 3. Combine binary data
        binary_payload = header + b"".join(byte_arrays)

        # 4. Encode to Base64 String
        encoded_str = base64.b64encode(binary_payload).decode('utf-8')

        msg = String()
        msg.data = encoded_str
        self.pub.publish(msg)

        with open(self.csv_file, "a", newline="") as f:
            csv.writer(f).writerow([self.msg_id, publish_time, "List[4]Base64String"])
        self.get_logger().info(f"🚀 Sent String-encoded List #{self.msg_id}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--folder', type=str, default='multi_array_string')
    args, _ = parser.parse_known_args()
    rclpy.init(args=sys.argv)
    node = ListPublisherString(args.folder)
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()