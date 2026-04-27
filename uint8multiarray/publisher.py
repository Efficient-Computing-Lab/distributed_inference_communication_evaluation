import rclpy
from rclpy.node import Node
from std_msgs.msg import UInt8MultiArray
import numpy as np
import time
import struct
import csv
import os


class BigPublisher(Node):
    def __init__(self):
        super().__init__('big_publisher')
        self.pub = self.create_publisher(UInt8MultiArray, 'big_topic', 10)
        self.timer = self.create_timer(5.0, self.send)
        self.dim = 6125
        self.msg_id = 0

        self.csv_file = 'publisher_log.csv'
        if not os.path.exists(self.csv_file):
            with open(self.csv_file, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['msg_id', 'publish_time', 'message_type'])

    def send(self):
        self.msg_id += 1
        publish_time = time.time()

        self.get_logger().info(f"🚀 Sending message #{self.msg_id}")

        arr = np.random.rand(self.dim, self.dim).astype(np.float32)
        arr = np.ascontiguousarray(arr, dtype=np.float32)
        raw_bytes = arr.tobytes()

        # ✅ FIXED STRUCT FORMAT
        header = struct.pack('=Id', self.msg_id, publish_time)

        msg = UInt8MultiArray()
        msg.data = header + raw_bytes

        self.pub.publish(msg)

        with open(self.csv_file, 'a', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([self.msg_id, publish_time, 'UInt8MultiArray'])


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