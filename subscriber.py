import rclpy
from rclpy.node import Node
from std_msgs.msg import UInt8MultiArray
import numpy as np
import time


class BigSubscriber(Node):
    def __init__(self):
        super().__init__('big_subscriber')
        self.sub = self.create_subscription(
            UInt8MultiArray,
            'big_topic',
            self.callback,
            10
        )

    def callback(self, msg):
        size_mb = len(msg.data) / (1024 * 1024)
        self.get_logger().info(f"📥 Received message size: {size_mb:.2f} MB")

        start_proc = time.perf_counter()

        # Process the data
        arr = np.frombuffer(msg.data, dtype=np.float32)
        # Note: We don't necessarily need to reshape if we just want the mean
        _ = arr.mean()

        proc_time = time.perf_counter() - start_proc

        self.get_logger().info(f"⚙️ Processing time: {proc_time:.6f} sec")

        # Current clock time in seconds
        finish_time = self.get_clock().now().nanoseconds / 1e9
        self.get_logger().info(f"📊 Callback finished at: {finish_time:.9f}")


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