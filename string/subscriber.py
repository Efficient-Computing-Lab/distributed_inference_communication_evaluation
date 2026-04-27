import rclpy
from rclpy.node import Node
from std_msgs.msg import String
import numpy as np
import time
import base64
import struct
import csv
import os


class BigSubscriber(Node):
    def __init__(self):
        super().__init__('big_subscriber')

        self.sub = self.create_subscription(
            String,
            'big_topic',
            self.callback,
            10
        )

        # CSV setup
        self.csv_file = "same_machine/subscriber_log.csv"
        if not os.path.exists(self.csv_file):
            with open(self.csv_file, "w", newline="") as f:
                csv.writer(f).writerow([
                    "msg_id",
                    "publish_time",
                    "receive_time",
                    "latency_sec",
                    "message_type"
                ])

    def callback(self, msg):
        receive_time = time.time()

        # 1. THE "DECODING TAX": Convert text back to binary
        # This is the line that adds ~0.4s of latency
        binary_data = base64.b64decode(msg.data)

        # 2. Extract the 12-byte header from the decoded binary
        msg_id, publish_time = struct.unpack_from('=Id', binary_data, 0)

        # 3. Extract and reshape the payload
        payload_bytes = binary_data[12:]
        arr = np.frombuffer(payload_bytes, dtype=np.float32).reshape(6125, 6125)

        latency = receive_time - publish_time
        self.get_logger().info(f"📥 Msg #{msg_id} | Latency: {latency:.6f}s")

        # Log to CSV
        with open(self.csv_file, "a", newline="") as f:
            csv.writer(f).writerow([msg_id, publish_time, receive_time, latency, "String(Base64)"])


def main():
    rclpy.init()
    node = BigSubscriber()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()