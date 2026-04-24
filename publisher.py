import rclpy
from rclpy.node import Node
from std_msgs.msg import UInt8MultiArray
import numpy as np
import time


class BigPublisher(Node):
    def __init__(self):
        super().__init__('big_publisher')
        self.pub = self.create_publisher(UInt8MultiArray, 'big_topic', 10)
        self.timer = self.create_timer(5.0, self.send)
        # 6125 * 6125 * 4 bytes (float32) ≈ 150,000,000 bytes
        self.dim = 6125

    def send(self):
        self.get_logger().info(f"🚀 Starting 150MB message generation...")
        start_gen = time.perf_counter()

        # Generation
        msg = UInt8MultiArray()
        arr = np.random.rand(self.dim, self.dim).astype(np.float32)
        msg.data = arr.tobytes()

        gen_time = time.perf_counter() - start_gen
        self.get_logger().info(f"🧠 Generation time: {gen_time:.3f} sec")

        # Publish call timing
        start_pub = time.perf_counter()
        self.pub.publish(msg)
        pub_call_time = time.perf_counter() - start_pub

        self.get_logger().info(f"📡 Publish call time: {pub_call_time:.6f} sec")
        self.get_logger().info(f"📦 Total publisher time: {(gen_time + pub_call_time):.3f} sec")


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