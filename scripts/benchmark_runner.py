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

    def get_cpu_softirq(self, duration: int = 3):
        res = self.run(f"mpstat 1 {duration} -o JSON")
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
            print(f"{Colors.GREEN}[+] Loading XDP-L2-Guard (STRICT NATIVE)...{Colors.END}")
            loader_path = os.path.join(self.project_root, "src/control_plane/loader.py")
            
            # Use --non-interactive (-n) to avoid hang
            res = self.run(f"sudo python3 {loader_path} -i {iface} -n")
            if res.returncode != 0:
                print(f"{Colors.RED}[!] Native XDP failed on {iface}. Skipping XDP.{Colors.END}")
                return

            check_link = self.run(f"ip link show {iface}")
            if "xdpdrv" not in check_link.stdout:
                print(f"{Colors.RED}[!] No xdpdrv found. Aborting.{Colors.END}")
                self.run(f"sudo ip link set dev {iface} xdp off")
                return
            
            print(f"{Colors.GREEN}[+] Native XDP Verified. Injecting IP...{Colors.END}")
            self.run("sudo bpftool map update name blacklist_ips key 0x03 0x00 0x00 0x0a value 0x00 0x00 0x00 0x00 0x00 0x00 0x00 0x00")

        subprocess.Popen(["ip", "netns", "exec", "ns1", "iperf3", "-s", "-D"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(1)

        print(f"{Colors.RED}[!] Starting 4-THREAD {packet_size}B Flood...{Colors.END}")
        ip1 = self.ns_config["ns1"]["ip"]
        flood_procs = []
        for _ in range(4):
            p = subprocess.Popen([
                "ip", "netns", "exec", "ns3", 
                "hping3", "--flood", "--udp", "-d", str(packet_size), "-a", self.ns_config["ns3"]["ip"], ip1
            ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL)
            flood_procs.append(p)

        try:
            print(f"{Colors.BLUE}[*] Measuring CPU SoftIRQ (3s)...{Colors.END}")
            softirq_val = self.get_cpu_softirq(duration=3)
            
            print(f"{Colors.BLUE}[*] Measuring Performance (3s)...{Colors.END}")
            iperf_res = self.run(f"ip netns exec ns2 iperf3 -c {ip1} -t 3 -u -b 10G --json")
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
        report_str = "\n" + "="*70 + "\n"
        report_str += f"{'MODE':<20} | {'Mbps':>10} | {'ms':>8} | {'LOSS%':>8} | {'SIQ%':>8}\n"
        report_str += "-" * 70 + "\n"
        for r in self.results:
            report_str += f"{r['mode']:<20} | {r['throughput_mbps']:>10} | {r['latency_ms']:>8} | {r['loss_percent']:>7}% | {r['softirq_percent']:>7}%\n"
        report_str += "="*70 + "\n"
        print(report_str)
        with open("benchmark_report.txt", "w") as f: f.write(report_str)
        self.plot_results()

    def plot_results(self):
        if not self.results: return
        modes = [r['mode'] for r in self.results]
        thru = [r['throughput_mbps'] for r in self.results]
        loss = [r['loss_percent'] for r in self.results]
        siq = [r['softirq_percent'] for r in self.results]
        x = np.arange(len(modes))
        width = 0.25
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 12))
        b1 = ax1.bar(x - width, thru, width, label='Mbps', color='#3498db')
        ax1_twin = ax1.twinx()
        b2 = ax1_twin.bar(x, siq, width, label='SIQ%', color='#e74c3c', alpha=0.7)
        ax1.set_title('Throughput vs CPU Overhead')
        ax1.set_xticks(x)
        ax1.set_xticklabels(modes, rotation=15)
        ax2.bar(x, loss, width*1.5, label='Loss%', color='#f1c40f')
        ax2.set_title('Packet Loss Comparison')
        ax2.set_xticks(x)
        ax2.set_xticklabels(modes, rotation=15)
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
            for size in [1400, 64]: bench.run_test(mode, packet_size=size)
        bench.report()
    finally:
        bench.cleanup()
