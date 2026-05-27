#!/usr/bin/env python3
import subprocess
import time
import json
import os
import sys
import argparse
import matplotlib.pyplot as plt
import numpy as np
from typing import Dict, List

class Colors:
    BLUE = "\033[94m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    BOLD = "\033[1m"
    END = "\033[0m"

class BenchmarkOrchestrator:
    def __init__(self, target_iface: str = None):
        self.br = "br0"
        self.ns_config = {
            "ns1": {"ip": "10.0.0.1", "mac": "00:00:00:00:00:01", "veth": "veth_ns1"},
            "ns2": {"ip": "10.0.0.2", "mac": "00:00:00:00:00:02", "veth": "veth_ns2"},
            "ns3": {"ip": "10.0.0.3", "mac": "00:00:00:00:00:03", "veth": "veth_ns3"},
        }
        self.target_iface = target_iface
        self.results = []
        self.project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

    def run(self, cmd: str, check: bool = True):
        return subprocess.run(cmd, shell=True, text=True, capture_output=True, check=check)

    def setup_network(self):
        print(f"{Colors.BLUE}[*] Building Network Namespaces...{Colors.END}")
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
        print(f"{Colors.YELLOW}[!] Cleaning up...{Colors.END}")
        for ns in self.ns_config:
            self.run(f"ip netns del {ns}", check=False)
        self.run(f"ip link del {self.br}", check=False)
        self.run("sudo pkill -9 iperf3", check=False)
        self.run("sudo pkill -9 hping3", check=False)
        if self.target_iface:
             self.run(f"ip link set dev {self.target_iface} xdp off 2>/dev/null", check=False)

    def get_cpu_softirq(self):
        res = self.run("mpstat 1 5 -o JSON")
        try:
            data = json.loads(res.stdout)
            stats = data['sysstat']['hosts'][0]['statistics']
            softirqs = [s['cpu-load'][0]['soft'] for s in stats]
            return round(sum(softirqs) / len(softirqs), 2)
        except:
            return 0.0

    def run_test(self, mode: str, packet_size: int = 64):
        label = "DDoS" if packet_size <= 64 else "Std"
        print(f"\n{Colors.BOLD}[>] Starting Benchmark: [{mode}] ({label}){Colors.END}")
        
        v_ns3_root = f"{self.ns_config['ns3']['veth']}_root"
        iface = self.target_iface if self.target_iface and mode == "xdp" else v_ns3_root

        self.run("sudo iptables -F")
        self.run(f"sudo ip link set dev {iface} xdp off 2>/dev/null", check=False)
        
        if mode == "iptables":
            print(f"{Colors.GREEN}[+] Applying 1000 iptables rules (Linear Scan)...{Colors.END}")
            for i in range(1000):
                self.run(f"sudo iptables -A FORWARD -s 1.2.3.{i%255} -j ACCEPT")
            mac3 = self.ns_config["ns3"]["mac"]
            self.run(f"sudo iptables -A FORWARD -m mac --mac-source {mac3} -j DROP")
        elif mode == "xdp":
            print(f"{Colors.GREEN}[+] Loading XDP-L2-Guard (O(1) Map Lookup)...{Colors.END}")
            loader_path = os.path.join(self.project_root, "src/control_plane/loader.py")
            # Attach and exit monitoring loop quickly
            attach_proc = subprocess.Popen(
                ["sudo", "python3", loader_path, "-i", iface, "--generic"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
            time.sleep(5)
            attach_proc.kill()
            
            print(f"{Colors.GREEN}[+] Injecting Attacker IP into Map...{Colors.END}")
            self.run("sudo bpftool map update name blacklist_ips key 0x03 0x00 0x00 0x0a value 0x00 0x00 0x00 0x00 0x00 0x00 0x00 0x00")

        subprocess.Popen(["ip", "netns", "exec", "ns1", "iperf3", "-s", "-D"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(1)

        print(f"{Colors.RED}[!] Starting 12-THREAD {packet_size}B Flood...{Colors.END}")
        ip1 = self.ns_config["ns1"]["ip"]
        flood_procs = []
        for _ in range(12):
            p = subprocess.Popen([
                "ip", "netns", "exec", "ns3", 
                "hping3", "--flood", "--udp", "-d", str(packet_size), "-a", self.ns_config["ns3"]["ip"], ip1
            ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL)
            flood_procs.append(p)

        try:
            print(f"{Colors.BLUE}[*] Measuring CPU SoftIRQ (5s)...{Colors.END}")
            softirq_val = self.get_cpu_softirq()
            
            print(f"{Colors.BLUE}[*] Measuring Performance...{Colors.END}")
            iperf_res = self.run(f"ip netns exec ns2 iperf3 -c {ip1} -t 5 -u -b 10G --json")
            data = json.loads(iperf_res.stdout)
            
            mbps = data['end']['sum']['bits_per_second'] / 1_000_000
            loss = data['end']['sum']['lost_percent']
            avg_lat = self.run(f"ip netns exec ns2 ping {ip1} -c 5 -q").stdout.split('/')[-3]

            self.results.append({
                "mode": f"{mode}_{label}",
                "throughput_mbps": round(mbps, 2),
                "latency_ms": avg_lat,
                "loss_percent": round(loss, 2),
                "softirq_percent": softirq_val
            })
            print(f"{Colors.GREEN}[+] {mbps:.2f} Mbps | Lat: {avg_lat}ms | Loss: {loss:.2f}% | SIQ: {softirq_val}%{Colors.END}")

        finally:
            for p in flood_procs: p.kill()
            self.run("sudo pkill -9 hping3", check=False)
            self.run("sudo pkill -9 iperf3", check=False)
            if mode == "xdp": self.run(f"sudo ip link set dev {iface} xdp off", check=False)

    def report(self):
        print("\n" + "="*60)
        print(f"{'MODE':<15} | {'Mbps':>8} | {'ms':>6} | {'LOSS%':>6} | {'SIQ%' :>6}")
        print("-" * 60)
        for r in self.results:
            print(f"{r['mode']:<15} | {r['throughput_mbps']:>8} | {r['latency_ms']:>6} | {r['loss_percent']:>5}% | {r['softirq_percent']:>5}%")
        print("="*60)
        self.plot_results()

    def plot_results(self):
        if not self.results: return
        modes = [r['mode'] for r in self.results]
        throughput = [r['throughput_mbps'] for r in self.results]
        softirq = [r['softirq_percent'] for r in self.results]
        
        std_res = [r for r in self.results if "Std" in r['mode']]
        ddos_res = [r for r in self.results if "DDoS" in r['mode']]
        
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 10))
        
        def draw(ax, data, title):
            labels = [r['mode'].split('_')[0] for r in data]
            x = np.arange(len(labels))
            width = 0.35
            b1 = ax.bar(x - width/2, [r['throughput_mbps'] for r in data], width, label='Mbps', color='skyblue')
            ax2 = ax.twinx()
            b2 = ax2.bar(x + width/2, [r['softirq_percent'] for r in data], width, label='SIQ%', color='salmon')
            ax.set_title(title)
            ax.set_xticks(x)
            ax.set_xticklabels(labels)
            ax.legend([b1, b2], ['Mbps', 'SoftIRQ %'], loc='upper left')

        if std_res: draw(ax1, std_res, "Standard (1400B)")
        if ddos_res: draw(ax2, ddos_res, "DDoS (64B)")
        plt.tight_layout()
        plt.savefig('benchmark_results.png')

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-i", "--interface", help="Target physical NIC")
    args = parser.parse_args()
    bench = BenchmarkOrchestrator(target_iface=args.interface)
    try:
        bench.cleanup()
        bench.setup_network()
        for mode in ["iptables", "xdp"]:
            for size in [1400, 64]:
                bench.run_test(mode, packet_size=size)
        bench.report()
    finally:
        bench.cleanup()
