import rclpy
from rclpy.node import Node
from std_msgs.msg import UInt8MultiArray
import numpy as np
import time
import struct
import csv
import os


class BigSubscriber(Node):
    def __init__(self):
        super().__init__('big_subscriber')
        self.sub = self.create_subscription(
            UInt8MultiArray,
            'big_topic',
            self.callback,
            10
        )

        self.csv_file = 'subscriber_log.csv'
        if not os.path.exists(self.csv_file):
            with open(self.csv_file, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['msg_id', 'publish_time', 'receive_time', 'latency_sec', 'message_type'])

    def callback(self, msg):
        receive_time = time.time()

        data_bytes = bytes(msg.data)

        try:
            msg_id, publish_time = struct.unpack_from('=Id', data_bytes, 0)

            latency = receive_time - publish_time

            self.get_logger().info(
                f"📥 Msg #{msg_id} | Latency: {latency:.6f}s"
            )

            payload = data_bytes[12:]
            arr = np.frombuffer(memoryview(payload), dtype=np.float32)
            _ = arr.mean()

            with open(self.csv_file, 'a', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([
                    msg_id,
                    publish_time,
                    receive_time,
                    latency,
                    'UInt8MultiArray'
                ])

        except Exception as e:
            self.get_logger().error(f"Failed to unpack: {e}")

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