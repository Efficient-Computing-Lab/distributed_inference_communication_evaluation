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


class BigSubscriber(Node):
    def __init__(self, folder_path):
        super().__init__('big_subscriber')
        self.sub = self.create_subscription(String, 'big_topic', self.callback, 10)

        if not os.path.exists(folder_path):
            os.makedirs(folder_path)

        self.csv_file = os.path.join(folder_path, "subscriber_log.csv")

        if not os.path.exists(self.csv_file):
            with open(self.csv_file, "w", newline="") as f:
                csv.writer(f).writerow(["msg_id", "publish_time", "receive_time", "latency_sec", "message_type"])

    def callback(self, msg):
        receive_time = time.time()
        binary = base64.b64decode(msg.data)
        msg_id, publish_time = struct.unpack_from('=Id', binary, 0)

        latency = receive_time - publish_time

        with open(self.csv_file, "a", newline="") as f:
            csv.writer(f).writerow([msg_id, publish_time, receive_time, latency, "String(Base64)"])

        self.get_logger().info(f"📥 Received #{msg_id} | Latency: {latency:.4f}s")


def main():
    parser = argparse.ArgumentParser(description='ROS 2 Big Data Subscriber')
    parser.add_argument('--folder', type=str, default='same_machine', help='Folder name')
    args, unknown = parser.parse_known_args()

    rclpy.init(args=sys.argv)
    node = BigSubscriber(args.folder)

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()