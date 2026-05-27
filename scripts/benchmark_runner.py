#!/usr/bin/env python3
import subprocess
import time
import json
import os
import sys
import argparse
from typing import Dict, List

class BenchmarkOrchestrator:
    def __init__(self):
        self.br = "br0"
        self.ns_config = {
            "ns1": {"ip": "10.0.0.1", "mac": "00:00:00:00:00:01", "veth": "veth_ns1"},
            "ns2": {"ip": "10.0.0.2", "mac": "00:00:00:00:00:02", "veth": "veth_ns2"},
            "ns3": {"ip": "10.0.0.3", "mac": "00:00:00:00:00:03", "veth": "veth_ns3"},
        }
        self.results = []

    def run(self, cmd: str, check: bool = True):
        return subprocess.run(cmd, shell=True, text=True, capture_output=True, check=check)

    def setup_network(self):
        print("🏗️  Building Network Namespaces...")
        self.run(f"ip link add {self.br} type bridge", check=False)
        self.run(f"ip link set {self.br} up")

        for ns, cfg in self.ns_config.items():
            v_root = f"{cfg['veth']}_root"
            v_ns = cfg['veth']
            
            self.run(f"ip netns add {ns}", check=False)
            self.run(f"ip link add {v_ns} type veth peer name {v_root}")
            self.run(f"ip link set {v_ns} netns {ns}")
            self.run(f"ip link set {v_root} master {self.br}")
            
            self.run(f"ip netns exec {ns} ip link set lo up")
            self.run(f"ip netns exec {ns} ip link set {v_ns} address {cfg['mac']}")
            self.run(f"ip netns exec {ns} ip link set {v_ns} up")
            self.run(f"ip netns exec {ns} ip addr add {cfg['ip']}/24 dev {v_ns}")
            
            self.run(f"ip link set {v_root} up")

    def cleanup(self):
        print("🧹 Cleaning up namespaces and bridges...")
        for ns in self.ns_config:
            self.run(f"ip netns del {ns}", check=False)
        self.run(f"ip link del {self.br}", check=False)
        self.run("pkill iperf3", check=False)
        self.run("pkill hping3", check=False)

    def run_test(self, mode: str):
        print(f"\n🚀 Starting Benchmark: [{mode}]")
        
        # Reset rules
        self.run("iptables -F")
        # TODO: Detach XDP
        
        if mode == "iptables":
            print("🛡️  Applying iptables rule...")
            mac3 = self.ns_config["ns3"]["mac"]
            self.run(f"iptables -A FORWARD -m mac --mac-source {mac3} -j DROP")
        elif mode == "xdp":
            print("🛡️  Loading XDP-L2-Guard...")
            # Placeholder for loader call
            # veth_root_ns3 = "veth_ns3_root"
            # self.run(f"python3 src/control_plane/loader.py -i {veth_root_ns3} ...")
            time.sleep(2)

        # Start iperf3 server in ns1
        print("📡 Starting iperf3 server in ns1...")
        subprocess.Popen(["ip", "netns", "exec", "ns1", "iperf3", "-s", "-D"])
        time.sleep(1)

        # Start Flood from ns3
        print("🔥 Starting UDP Flood from ns3...")
        ip1 = self.ns_config["ns1"]["ip"]
        flood_proc = subprocess.Popen([
            "ip", "netns", "exec", "ns3", 
            "hping3", "--flood", "--udp", "-a", self.ns_config["ns3"]["ip"], ip1
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        try:
            print("📊 Measuring Throughput (ns2 -> ns1)...")
            iperf_res = self.run(f"ip netns exec ns2 iperf3 -c {ip1} -t 10 --json")
            data = json.loads(iperf_res.stdout)
            bps = data['end']['sum_received']['bits_per_second']
            mbps = bps / 1_000_000

            print("📊 Measuring Latency...")
            ping_res = self.run(f"ip netns exec ns2 ping {ip1} -c 10 -q")
            # Extract avg latency from: rtt min/avg/max/mdev = 0.038/0.054/0.071/0.010 ms
            avg_lat = ping_res.stdout.split('/')[-3]

            self.results.append({
                "mode": mode,
                "throughput_mbps": round(mbps, 2),
                "latency_ms": avg_lat
            })
            
            print(f"✅ Results: {mbps:.2f} Mbps | {avg_lat} ms")

        finally:
            flood_proc.terminate()
            self.run("pkill iperf3", check=False)

    def report(self):
        print("\n" + "="*40)
        print(f"{'MODE':<15} | {'THROUGHPUT':<12} | {'LATENCY':<10}")
        print("-" * 40)
        for r in self.results:
            print(f"{r['mode']:<15} | {r['throughput_mbps']:>7} Mbps | {r['latency_ms']:>7} ms")
        print("="*40)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--cleanup", action="store_true")
    args = parser.parse_args()

    bench = BenchmarkOrchestrator()
    if args.cleanup:
        bench.cleanup()
        sys.exit(0)

    try:
        bench.cleanup() # Initial sweep
        bench.setup_network()
        bench.run_test("baseline") # No rules
        bench.run_test("iptables")
        # bench.run_test("xdp")
        bench.report()
    finally:
        bench.cleanup()
