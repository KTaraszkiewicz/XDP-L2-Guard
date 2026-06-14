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
    """Helper function to execute shell commands"""
    return subprocess.run(cmd, shell=True, text=True, capture_output=True)

def main():
    parser = argparse.ArgumentParser(description="XDP-L2-Guard CO-RE Control Plane")
    parser.add_argument("-i", "--interface", required=True, help="Network interface, e.g., eth0")
    parser.add_argument("--generic", action="store_true", help="Force XDP generic mode (xdpgeneric)")
    parser.add_argument("-n", "--non-interactive", action="store_true", help="Exit after attachment (no monitoring loop)")
    args = parser.parse_args()

    logger = setup_logger()
    interface = args.interface

    # Paths
    control_plane_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.abspath(os.path.join(control_plane_dir, "../../"))
    bpf_obj_file = os.path.join(project_root, "src/data_plane/filter.o")

    logger.info(f"Initializing CO-RE engine on interface: {interface}")

    # 1. Ahead-of-Time compilation via Makefile
    logger.info("Triggering Ahead-of-Time (AOT) compilation...")
    compile_res = run_cmd(f"cd {project_root} && make")
    if compile_res.returncode != 0:
        logger.error(f"CO-RE compilation error:\n{compile_res.stderr}")
        sys.exit(1)
    
    if not os.path.exists(bpf_obj_file):
        logger.error("Critical error: Compiled filter.o file not found!")
        sys.exit(1)

    # 2. Select execution mode (Native / Generic)
    xdp_mode = "xdpgeneric" if args.generic else "xdpdrv"
    if not args.generic:
        logger.info("Requesting high-performance mode: attaching in Native (xdpdrv)...")

    # 3. Attach ELF object to the network interface using native iproute2
    # Clean previous rules to remove potential "zombie" programs
    run_cmd(f"ip link set dev {interface} xdpgeneric off")
    run_cmd(f"ip link set dev {interface} xdpdrv off")
    run_cmd(f"ip link set dev {interface} xdp off") 
    
    # -force flag: Ensures overwriting of old XDP programs in the kernel
    attach_cmd = f"ip -force link set dev {interface} {xdp_mode} obj {bpf_obj_file} sec xdp"
    attach_res = run_cmd(attach_cmd)
    
    if attach_res.returncode != 0:
        logger.error(f"Critical error mounting subsystem:\n{attach_res.stderr}")
        logger.info(f"Hint: Ensure you have disabled hardware offloading using: sudo ethtool -K {interface} gro off gso off")
        sys.exit(1)

    logger.info("Successfully attached CO-RE ELF to the eXpress Data Path.")
    
    if args.non_interactive:
        logger.info("Non-interactive mode: Exiting.")
        return

    logger.info("Engine running. Asynchronous monitoring active (press Ctrl+C to abort).")

    # 4. Polling eBPF maps via bpftool
    try:
        while True:
            time.sleep(1)
            # Dump action_map map in JSON format
            dump_res = run_cmd("bpftool -j map dump name action_map")
            
            if dump_res.returncode == 0 and dump_res.stdout.strip():
                map_data = json.loads(dump_res.stdout)
                
                if len(map_data) > 0:
                    print("\n" + "━"*50)
                    logger.info("Active drops at the eXpress Data Path layer:")
                    
                    for item in map_data:
                        # BTF mode returns structured JSON
                        try:
                            key_val = item["key"]
                            val_obj = item["value"]
                            drop_count = val_obj["dropped_packets"]
                            ip_addr = int_to_ip(key_val)
                            logger.info(f" ➔ Source address [{ip_addr}] blocked: {drop_count} frames")
                        except:
                            # Fallback for raw hex
                            key_bytes = [int(x, 16) for x in item["key"]]
                            val_bytes = [int(x, 16) for x in item["value"]]
                            ip_int = struct.unpack("<I", bytes(key_bytes))[0]
                            drop_count = struct.unpack("<Q", bytes(val_bytes[16:24]))[0]
                            ip_addr = int_to_ip(ip_int)
                            logger.info(f" ➔ Source address [{ip_addr}] blocked: {drop_count} frames")
                    print("━"*50)
                else:
                    sys.stdout.write("🛡️ ")
                    sys.stdout.flush()
            else:
                sys.stdout.write("🛡️ ")
                sys.stdout.flush()

    except KeyboardInterrupt:
        print("\n")
        logger.info("SIGINT caught. Dismantling Data Plane logic...")
    finally:
        # 5. Safe detachment of CO-RE environment
        run_cmd(f"ip link set dev {interface} {xdp_mode} off")
        run_cmd(f"ip link set dev {interface} xdp off")
        logger.info(f"Rules detached from {interface}. DMA memory released.")

if __name__ == "__main__":
    main()
