import rclpy
from rclpy.node import Node
from std_msgs.msg import String
import numpy as np
import time
import base64
import struct
import csv
import os


class BigPublisher(Node):
    def __init__(self):
        super().__init__('big_publisher')

        self.pub = self.create_publisher(String, 'big_topic', 10)
        self.timer = self.create_timer(5.0, self.send)

        self.dim = 6125
        self.msg_id = 0

        # CSV setup
        self.csv_file = "same_machine/publisher_log.csv"
        if not os.path.exists(self.csv_file):
            with open(self.csv_file, "w", newline="") as f:
                csv.writer(f).writerow(
                    ["msg_id", "publish_time", "message_type"]
                )

    def send(self):
        self.msg_id += 1
        publish_time = time.time()
        self.get_logger().info(f"🚀 Sending String(Base64) msg #{self.msg_id}")

        # 1. Create the 150MB float32 array
        arr = np.random.rand(self.dim, self.dim).astype(np.float32)

        # 2. Convert to raw bytes + 12-byte header
        header = struct.pack('=Id', self.msg_id, publish_time)
        binary_payload = header + arr.tobytes()

        # 3. THE "STRING TAX": Encode binary to Base64 text
        # This turns 150MB of binary into ~200MB of ASCII text
        encoded_str = base64.b64encode(binary_payload).decode('utf-8')

        # 4. Publish as a standard ROS String
        msg = String()
        msg.data = encoded_str
        self.pub.publish(msg)

        # Log to CSV
        with open(self.csv_file, "a", newline="") as f:
            csv.writer(f).writerow([self.msg_id, publish_time, "String(Base64)"])


def main():
    rclpy.init()
    node = BigPublisher()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()