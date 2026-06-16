#!/usr/bin/env python3
import sys
import time
import subprocess
import json
import socket
import struct
import os

def run_cmd(cmd):
    return subprocess.run(cmd, shell=True, text=True, capture_output=True)

def get_map_id(name):
    res = run_cmd(f"bpftool map list | grep -m 1 {name}")
    if res.returncode != 0 or not res.stdout:
        return None
    return res.stdout.split(":")[0].strip()

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

def main():
    # BPF map names are limited to 15 chars, so 'source_stats_map' truncates to 'source_stats_ma'
    map_id = get_map_id("source_stats_ma")
    
    if not map_id:
        print("Error: source_stats_ma not found. Is the XDP program loaded?")
        sys.exit(1)

    print(f"Monitoring map ID: {map_id}. Press Ctrl+C to stop.")
    
    try:
        while True:
            res = run_cmd(f"bpftool -j map dump id {map_id}")
            if res.returncode == 0 and res.stdout:
                data = json.loads(res.stdout)
                stats = []
                for item in data:
                    ip = socket.inet_ntoa(bytes([int(x, 16) for x in item["key"]]))
                    count = struct.unpack("<Q", bytes([int(x, 16) for x in item["value"]]))[0]
                    stats.append((ip, count))
                
                stats.sort(key=lambda x: x[1], reverse=True)
                
                clear_screen()
                print("=== XDP Telemetry: Packets per Source IP ===")
                print(f"{'SOURCE IP':<18} | {'PACKETS':<10}")
                print("-" * 31)
                for ip, count in stats:
                    print(f"{ip:<18} | {count:<10}")
                
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\nExiting...")
        sys.exit(0)

if __name__ == "__main__":
    main()
