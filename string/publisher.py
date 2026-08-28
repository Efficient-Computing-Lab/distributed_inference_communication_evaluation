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


class BigPublisher(Node):
    def __init__(self, folder_path):
        super().__init__('big_publisher')
        self.pub = self.create_publisher(String, 'big_topic', 10)
        self.timer = self.create_timer(5.0, self.send)
        self.dim = 6125
        self.msg_id = 0

        # Create folder if it doesn't exist
        if not os.path.exists(folder_path):
            os.makedirs(folder_path)

        self.csv_file = os.path.join(folder_path, "publisher_log.csv")

        if not os.path.exists(self.csv_file):
            with open(self.csv_file, "w", newline="") as f:
                csv.writer(f).writerow(["msg_id", "publish_time", "message_type"])

    def send(self):
        self.msg_id += 1

        # Clock starts here, before the test data is created, so latency covers the whole
        # path: making the payload, packing it, and moving it. Every method in this repo
        # uses this same start point so the numbers are directly comparable.
        publish_time = time.time()

        arr = np.random.rand(self.dim, self.dim).astype(np.float32)

        header = struct.pack('=Id', self.msg_id, publish_time)
        binary_payload = header + arr.tobytes()
        encoded_str = base64.b64encode(binary_payload).decode('utf-8')

        msg = String()
        msg.data = encoded_str
        self.pub.publish(msg)

        with open(self.csv_file, "a", newline="") as f:
            csv.writer(f).writerow([self.msg_id, publish_time, "String(Base64)"])

        self.get_logger().info(f"🚀 Sent msg #{self.msg_id} to {self.csv_file}")


def main():
    # 1. Setup Argparse
    parser = argparse.ArgumentParser(description='ROS 2 Big Data Publisher')
    parser.add_argument('--folder', type=str, default='same_machine',
                        help='Folder name to save the CSV logs')

    # 2. Extract known arguments, ignore ROS-specific args
    args, unknown = parser.parse_known_args()

    # 3. Initialize ROS
    rclpy.init(args=sys.argv)
    node = BigPublisher(args.folder)

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()