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
        self.csv_file = "subscriber_log.csv"
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

        # Decode Base64 → binary
        binary = base64.b64decode(msg.data)

        # Extract header (SAME AS UInt8MultiArray VERSION)
        msg_id, publish_time = struct.unpack('=Id', binary[:12])
        payload = binary[12:]

        # Latency
        latency = receive_time - publish_time

        # Process payload
        arr = np.frombuffer(payload, dtype=np.float32)
        _ = arr.mean()

        self.get_logger().info(
            f"📥 Msg #{msg_id} | latency: {latency:.6f} sec"
        )

        # Log subscriber CSV
        with open(self.csv_file, "a", newline="") as f:
            csv.writer(f).writerow([
                msg_id,
                publish_time,
                receive_time,
                latency,
                "String(Base64)"
            ])


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