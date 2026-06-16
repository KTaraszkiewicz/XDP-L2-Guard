#!/usr/bin/env python3
import time
import sys
import os
import argparse
import subprocess
import json
import struct

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from utils import setup_logger, int_to_ip

def run_cmd(cmd):
    return subprocess.run(cmd, shell=True, text=True, capture_output=True)

def main():
    parser = argparse.ArgumentParser(description="XDP-L2-Guard CO-RE Control Plane")
    parser.add_argument("-i", "--interface", required=True, help="Network interface")
    parser.add_argument("--generic", action="store_true", help="Force XDP generic mode")
    parser.add_argument("-n", "--non-interactive", action="store_true", help="Exit after attachment")
    args = parser.parse_args()

    logger = setup_logger()
    interface = args.interface
    control_plane_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.abspath(os.path.join(control_plane_dir, "../../"))
    bpf_obj_file = os.path.join(project_root, "src/data_plane/filter.o")

    logger.info(f"Initializing engine on {interface}")

    compile_res = run_cmd(f"make -C {project_root}")
    if compile_res.returncode != 0:
        logger.error(f"Compilation error:\n{compile_res.stderr}")
        sys.exit(1)
    
    if not os.path.exists(bpf_obj_file):
        logger.error("Error: filter.o not found")
        sys.exit(1)

    xdp_mode = "xdpgeneric" if args.generic else "xdpdrv"
    if not args.generic:
        logger.info("Attaching in native mode")

    run_cmd(f"ip link set dev {interface} xdpgeneric off")
    run_cmd(f"ip link set dev {interface} xdpdrv off")
    run_cmd(f"ip link set dev {interface} xdp off") 
    
    attach_res = run_cmd(f"ip -force link set dev {interface} {xdp_mode} obj {bpf_obj_file} sec xdp")
    
    if attach_res.returncode != 0:
        logger.error(f"Mount error:\n{attach_res.stderr}")
        sys.exit(1)

    logger.info("Attached to XDP")
    
    if args.non_interactive:
        return

    logger.info("Monitoring active (Ctrl+C to abort)")

    try:
        while True:
            time.sleep(1)
            dump_res = run_cmd("bpftool -j map dump name action_map")
            
            if dump_res.returncode == 0 and dump_res.stdout.strip():
                map_data = json.loads(dump_res.stdout)
                if map_data:
                    print("\n" + "-"*50)
                    logger.info("Active drops:")
                    for item in map_data:
                        try:
                            drop_count = item["value"]["dropped_packets"]
                            ip_addr = int_to_ip(item["key"])
                            logger.info(f" -> Source [{ip_addr}] blocked: {drop_count} pkts")
                        except Exception:
                            key_bytes = bytes([int(x, 16) for x in item["key"]])
                            val_bytes = bytes([int(x, 16) for x in item["value"]])
                            ip_addr = int_to_ip(struct.unpack("<I", key_bytes)[0])
                            drop_count = struct.unpack("<Q", val_bytes[16:24])[0]
                            logger.info(f" -> Source [{ip_addr}] blocked: {drop_count} pkts")
                    print("-"*50)
                else:
                    sys.stdout.write(". ")
                    sys.stdout.flush()
            else:
                sys.stdout.write(". ")
                sys.stdout.flush()

    except KeyboardInterrupt:
        print()
        logger.info("SIGINT caught. Dismantling...")
    finally:
        run_cmd(f"ip link set dev {interface} {xdp_mode} off")
        run_cmd(f"ip link set dev {interface} xdp off")
        logger.info(f"Detached from {interface}")

if __name__ == "__main__":
    main()
