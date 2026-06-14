#!/usr/bin/env python3
import sys
import argparse
import subprocess
import socket
import struct
import json

# Action targets
ACTION_PASS = 0
ACTION_DROP = 1
ACTION_TX = 2
ACTION_REDIRECT = 3
ACTION_NAT = 4

def run_cmd(cmd):
    return subprocess.run(cmd, shell=True, text=True, capture_output=True)

def ip_to_hex(ip):
    # Convert IP to network byte order hex string for bpftool
    packed = socket.inet_aton(ip)
    # bpftool wants "0a 00 00 02"
    return " ".join([f"{b:02x}" for b in packed])

def int_to_ip(n):
    return socket.inet_ntoa(struct.pack("<I", n))

def get_map_id(name):
    res = run_cmd(f"bpftool map list | grep -m 1 {name}")
    if res.returncode != 0 or not res.stdout:
        return None
    return res.stdout.split(":")[0].strip()

def get_ifindex(iface):
    try:
        with open(f"/sys/class/net/{iface}/ifindex", "r") as f:
            return int(f.read().strip())
    except:
        return None

def main():
    parser = argparse.ArgumentParser(description="XDP-L2-Guard CLI (iptables style)")
    parser.add_argument("-A", "--append", action="store_true", help="Add a rule")
    parser.add_argument("-D", "--delete", action="store_true", help="Delete a rule")
    parser.add_argument("-L", "--list", action="store_true", help="List rules")
    parser.add_argument("-s", "--source", help="Source IP address")
    parser.add_argument("-j", "--jump", choices=["PASS", "DROP", "TX", "REDIRECT", "NAT"], help="Action target")
    parser.add_argument("--to-destination", help="NAT destination IP")
    parser.add_argument("--oif", help="Redirect output interface")

    args = parser.parse_args()

    act_map_id = get_map_id("action_map")
    dev_map_id = get_map_id("dev_map")

    if not act_map_id:
        print("Error: action_map not found. Is XDP loader running?")
        sys.exit(1)

    if args.list:
        print(f"{'SOURCE IP':<15} | {'ACTION':<10} | {'DETAILS'}")
        print("-" * 45)
        res = run_cmd(f"bpftool -j map dump id {act_map_id}")
        if res.stdout:
            data = json.loads(res.stdout)
            for item in data:
                key_bytes = [int(x, 16) for x in item["key"]]
                val_bytes = [int(x, 16) for x in item["value"]]
                
                # key is IP (network byte order in packet, but bpftool hex is just bytes)
                ip = socket.inet_ntoa(bytes(key_bytes))
                
                # value is struct action_cfg: target(4), new_ip(4), ifindex(4)
                target, new_ip, ifindex = struct.unpack("<III", bytes(val_bytes))
                
                actions = ["PASS", "DROP", "TX", "REDIRECT", "NAT"]
                act_str = actions[target] if target < len(actions) else "UNKNOWN"
                
                details = ""
                if target == ACTION_NAT:
                    details = f"to {socket.inet_ntoa(struct.pack('<I', new_ip))}"
                elif target == ACTION_REDIRECT:
                    details = f"to ifindex {ifindex}"
                
                print(f"{ip:<15} | {act_str:<10} | {details}")
        return

    if args.append:
        if not args.destination or not args.jump:
            print("Error: -A requires -d <IP> and -j <ACTION>")
            sys.exit(1)

        target = {
            "PASS": ACTION_PASS,
            "DROP": ACTION_DROP,
            "TX": ACTION_TX,
            "REDIRECT": ACTION_REDIRECT,
            "NAT": ACTION_NAT
        }[args.jump]

        new_ip_int = 0
        if args.jump == "NAT":
            if not args.to_destination:
                print("Error: NAT requires --to-destination <IP>")
                sys.exit(1)
            new_ip_int = struct.unpack("<I", socket.inet_aton(args.to_destination))[0]

        ifindex = 0
        if args.jump == "REDIRECT":
            if not args.oif:
                print("Error: REDIRECT requires --oif <IFACE>")
                sys.exit(1)
            ifindex = get_ifindex(args.oif)
            if not ifindex:
                print(f"Error: Interface {args.oif} not found")
                sys.exit(1)
            
            # Update dev_map too
            ifindex_hex = " ".join([f"{b:02x}" for b in struct.pack("<I", ifindex)])
            run_cmd(f"bpftool map update id {dev_map_id} key hex {ifindex_hex} value hex {ifindex_hex}")

        # struct action_cfg: target(4), new_ip(4), ifindex(4)
        val_hex = " ".join([f"{b:02x}" for b in struct.pack("<III", target, new_ip_int, ifindex)])
        res = run_cmd(f"bpftool map update id {act_map_id} key hex {ip_to_hex(args.destination)} value hex {val_hex}")
        
        if res.returncode == 0:
            print(f"Added rule: {args.destination} -> {args.jump}")
        else:
            print(f"Error adding rule: {res.stderr}")

    elif args.delete:
        if not args.destination:
            print("Error: -D requires -d <IP>")
            sys.exit(1)
        
        res = run_cmd(f"bpftool map delete id {act_map_id} key hex {ip_to_hex(args.destination)}")
        if res.returncode == 0:
            print(f"Deleted rule for {args.destination}")
        else:
            print(f"Error deleting rule: {res.stderr}")

if __name__ == "__main__":
    main()
