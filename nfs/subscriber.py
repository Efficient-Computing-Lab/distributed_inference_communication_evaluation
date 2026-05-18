import rclpy
from rclpy.node import Node
from std_msgs.msg import String
import numpy as np
import time
import struct
import base64
import csv
import os
import argparse
import sys


class NfsSubscriber(Node):
    def __init__(self, folder_path, nfs_path):
        super().__init__('nfs_subscriber')
        self.sub = self.create_subscription(String, 'nfs_topic', self.callback, 10)
        self.nfs_path = nfs_path

        if not os.path.exists(folder_path):
            os.makedirs(folder_path)

        self.csv_file = os.path.join(folder_path, "subscriber_log.csv")

        if not os.path.exists(self.csv_file):
            with open(self.csv_file, "w", newline="") as f:
                csv.writer(f).writerow([
                    "msg_id", "publish_time", "receive_time",
                    "read_done_time", "total_latency_sec", "read_time_sec", "message_type"
                ])

    def callback(self, msg):
        receive_time = time.time()

        header = base64.b64decode(msg.data)
        msg_id, publish_time = struct.unpack_from('=Id', header, 0)

        nfs_file = os.path.join(self.nfs_path, f"{msg_id}.npy")
        arr = np.load(nfs_file)

        read_done_time = time.time()
        read_time = read_done_time - receive_time
        total_latency = read_done_time - publish_time

        with open(self.csv_file, "a", newline="") as f:
            csv.writer(f).writerow([
                msg_id, publish_time, receive_time,
                read_done_time, total_latency, read_time, "NFS+String(notify)"
            ])

        self.get_logger().info(
            f"Received #{msg_id} | Total latency: {total_latency:.4f}s | NFS read: {read_time:.4f}s"
        )


def main():
    parser = argparse.ArgumentParser(description='ROS 2 NFS Subscriber')
    parser.add_argument('--folder', type=str, default='same_machine',
                        help='Folder name to save the CSV logs')
    parser.add_argument('--nfs-path', type=str, default='/var/locally-mounted',
                        help='Path to the NFS-mounted directory for data files')

    args, unknown = parser.parse_known_args()

    rclpy.init(args=sys.argv)
    node = NfsSubscriber(args.folder, args.nfs_path)

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
