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


class BigPublisher(Node):
    def __init__(self, folder_path):
        super().__init__('big_publisher')
        self.pub = self.create_publisher(UInt8MultiArray, 'big_topic', 10)
        self.timer = self.create_timer(5.0, self.send)
        self.dim = 6125
        self.msg_id = 0

        # Ensure directory exists
        if not os.path.exists(folder_path):
            os.makedirs(folder_path)

        self.csv_file = os.path.join(folder_path, 'publisher_log.csv')

        if not os.path.exists(self.csv_file):
            with open(self.csv_file, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['msg_id', 'publish_time', 'message_type'])

    def send(self):
        self.msg_id += 1

        # 1. Create the 150MB float32 array
        arr = np.random.rand(self.dim, self.dim).astype(np.float32)

        # Stamped after data generation so latency measures the method
        # (serialization + DDS transport), not the harness's numpy RNG.
        publish_time = time.time()

        # 2. Convert to raw bytes
        raw_bytes = arr.tobytes()

        # 3. Create the 12-byte header
        header = struct.pack('=Id', self.msg_id, publish_time)

        # 4. Combine and publish
        msg = UInt8MultiArray()
        msg.data = header + raw_bytes
        self.pub.publish(msg)

        self.get_logger().info(f"🚀 Sending message #{self.msg_id}")

        # Log to CSV
        with open(self.csv_file, 'a', newline='') as f:
            csv.writer(f).writerow([self.msg_id, publish_time, 'UInt8MultiArray'])


def main():
    parser = argparse.ArgumentParser(description='ROS 2 Binary Publisher')
    parser.add_argument('--folder', type=str, default='same_machine', help='Folder name')
    args, unknown = parser.parse_known_args()

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