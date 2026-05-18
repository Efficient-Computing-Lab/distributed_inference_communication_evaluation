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


class NfsPublisher(Node):
    def __init__(self, folder_path, nfs_path):
        super().__init__('nfs_publisher')
        self.pub = self.create_publisher(String, 'nfs_topic', 10)
        self.timer = self.create_timer(5.0, self.send)
        self.dim = 6125
        self.msg_id = 0
        self.nfs_path = nfs_path

        if not os.path.exists(nfs_path):
            os.makedirs(nfs_path)

        if not os.path.exists(folder_path):
            os.makedirs(folder_path)

        self.csv_file = os.path.join(folder_path, "publisher_log.csv")

        if not os.path.exists(self.csv_file):
            with open(self.csv_file, "w", newline="") as f:
                csv.writer(f).writerow(["msg_id", "publish_time", "write_time_sec", "message_type"])

    def send(self):
        self.msg_id += 1

        arr = np.random.rand(self.dim, self.dim).astype(np.float32)

        publish_time = time.time()

        # Write array to NFS
        nfs_file = os.path.join(self.nfs_path, f"{self.msg_id}.npy")
        np.save(nfs_file, arr)

        write_done_time = time.time()
        write_time = write_done_time - publish_time

        # Send lightweight notification: msg_id + publish_time encoded in the String message
        header = struct.pack('=Id', self.msg_id, publish_time)
        msg = String()
        msg.data = base64.b64encode(header).decode('utf-8')
        self.pub.publish(msg)

        with open(self.csv_file, "a", newline="") as f:
            csv.writer(f).writerow([self.msg_id, publish_time, write_time, "NFS+String(notify)"])

        self.get_logger().info(f"Sent msg #{self.msg_id} | NFS write: {write_time:.4f}s")


def main():
    parser = argparse.ArgumentParser(description='ROS 2 NFS Publisher')
    parser.add_argument('--folder', type=str, default='same_machine',
                        help='Folder name to save the CSV logs')
    parser.add_argument('--nfs-path', type=str, default='/mnt/myshareddir',
                        help='Path to the NFS-mounted directory for data files')

    args, unknown = parser.parse_known_args()

    rclpy.init(args=sys.argv)
    node = NfsPublisher(args.folder, args.nfs_path)

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
