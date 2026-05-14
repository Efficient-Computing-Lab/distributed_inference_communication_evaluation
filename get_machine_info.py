
import socket 
import platform
from datetime import datetime
import os
import json 

def get_machine_info():
    info = {}

    info["hostname"] = socket.gethostname()
    info["platform"] = platform.platform()
    info["system"] = platform.system()
    info["release"] = platform.release()
    info["machine"] = platform.machine()
    info["processor"] = platform.processor()
    info["python_version"] = platform.python_version()

    # CPU info (Linux)
    try:
        with open("/proc/cpuinfo", "r") as f:
            cpuinfo = f.read()

        model_name = None
        cpu_count = 0

        for line in cpuinfo.splitlines():
            if "model name" in line and model_name is None:
                model_name = line.split(":")[1].strip()

            if line.startswith("processor"):
                cpu_count += 1

        info["cpu_model"] = model_name
        info["cpu_cores"] = cpu_count

    except Exception:
        info["cpu_model"] = "Unknown"
        info["cpu_cores"] = "Unknown"
    # RAM info (Linux)
    try:
        with open("/proc/meminfo", "r") as f:
            meminfo = f.read()

        for line in meminfo.splitlines():
            if line.startswith("MemTotal"):
                # Example line:
                # MemTotal:       32768000 kB

                mem_kb = int(line.split(":")[1].strip().split()[0])

                mem_mb = mem_kb / 1024
                mem_gb = mem_mb / 1024

                info["memory_total_mb"] = round(mem_mb, 2)
                info["memory_total_gb"] = round(mem_gb, 2)

                break

    except Exception:
        info["memory_total_mb"] = "Unknown"
        info["memory_total_gb"] = "Unknown"
    # RAM info (Linux)
    # try:
    #     with open("/proc/meminfo", "r") as f:
    #         meminfo = f.read()

    #     for line in meminfo.splitlines():
    #         if line.startswith("MemTotal"):
    #             info["memory_total"] = line.split(":")[1].strip()
    #             break

    # except Exception:
    #     info["memory_total"] = "Unknown"

    return info

if __name__ == '__main__':
    info = get_machine_info()
    print(json.dumps(info))
    # print(info)
    # timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    # machine_info_path = os.path.join(f"{timestamp}_machine_info_remote.json")

    # with open(machine_info_path, "w") as f:
    #     json.dump(info, f, indent=4)