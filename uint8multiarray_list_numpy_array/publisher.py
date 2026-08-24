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


class ListPublisherUInt8(Node):
    def __init__(self, folder_path):
        super().__init__('list_publisher_uint8')
        self.pub = self.create_publisher(UInt8MultiArray, 'big_topic', 10)
        self.timer = self.create_timer(5.0, self.send)
        self.msg_id = 0

        self.shapes = [
            (1, 120, 160, 5, 64),
            (1, 120, 160, 5, 64, 3),
            (1, 120, 160, 6),
            (1, 120, 160)
        ]

        os.makedirs(folder_path, exist_ok=True)
        self.csv_file = os.path.join(folder_path, "publisher_log.csv")

        if not os.path.exists(self.csv_file):
            with open(self.csv_file, "w", newline="") as f:
                csv.writer(f).writerow(["msg_id", "publish_time", "message_type"])

    def send(self):
        self.msg_id += 1

        arrays = [np.random.rand(*s).astype(np.float32) for s in self.shapes]

        # Stamped after data generation so latency measures the method
        # (packing + DDS transport), not the harness's numpy RNG.
        publish_time = time.time()

        byte_arrays = [a.tobytes() for a in arrays]
        lengths = [len(b) for b in byte_arrays]

        header = struct.pack('=Id4I', self.msg_id, publish_time, *lengths)
        binary_payload = header + b"".join(byte_arrays)

        # Convert bytes → list[int] for UInt8MultiArray
        msg = UInt8MultiArray()
        msg.data = list(binary_payload)

        self.pub.publish(msg)

        with open(self.csv_file, "a", newline="") as f:
            csv.writer(f).writerow([self.msg_id, publish_time, "List[4]UInt8MultiArray"])

        self.get_logger().info(f"🚀 Sent UInt8MultiArray #{self.msg_id}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--folder', type=str, default='multi_array_uint8')
    args, _ = parser.parse_known_args()

    rclpy.init(args=sys.argv)
    node = ListPublisherUInt8(args.folder)

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass

    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()