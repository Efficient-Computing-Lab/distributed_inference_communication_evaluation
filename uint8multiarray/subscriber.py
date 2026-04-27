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

        self.csv_file = 'same_machine/subscriber_log.csv'
        if not os.path.exists(self.csv_file):
            with open(self.csv_file, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['msg_id', 'publish_time', 'receive_time', 'latency_sec', 'message_type'])

    def callback(self, msg):
        receive_time = time.time()

        # Convert ROS data to standard Python bytes
        data_bytes = bytes(msg.data)

        try:
            # 1. Extract the 12-byte header
            msg_id, publish_time = struct.unpack_from('=Id', data_bytes, 0)

            # 2. Slice the remaining bytes (the payload)
            payload = data_bytes[12:]

            # 3. Use frombuffer to "re-interpret" bytes as float32
            # We then reshape it back to the original square dimensions
            arr = np.frombuffer(payload, dtype=np.float32).reshape(6125, 6125)

            # Performance check (optional)
            _ = arr.mean()

            latency = receive_time - publish_time
            self.get_logger().info(f"📥 Msg #{msg_id} | Latency: {latency:.6f}s")

            # Log to CSV
            with open(self.csv_file, 'a', newline='') as f:
                csv.writer(f).writerow([msg_id, publish_time, receive_time, latency, 'UInt8MultiArray'])

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