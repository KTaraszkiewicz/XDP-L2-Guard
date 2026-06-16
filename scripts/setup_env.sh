#!/bin/bash

# XDP-L2-Guard Environment Setup
# Targeted for Ubuntu 24.04+ (Kernel 5.15+)

set -e

echo "-------------------------------------------------------"
echo "🛡️  Starting XDP-L2-Guard Environment Configuration"
echo "-------------------------------------------------------"

# 1. Update and install toolchain
echo "[*] Installing eBPF Toolchain & Development Tools..."
sudo apt update
sudo apt install -y \
    clang \
    llvm \
    libbpf-dev \
    linux-headers-$(uname -r) \
    linux-tools-common \
    linux-tools-$(uname -r) \
    gcc \
    make \
    pkg-config

# 2. Install Benchmarking & Monitoring Tools
echo "[*] Installing Benchmarking Suite (iperf3, hping3, sysstat)..."
sudo apt install -y \
    hping3 \
    iperf3 \
    sysstat \
    jq \
    ethtool \
    net-tools

# 3. Install Python Dependencies for Orchestrator & Graphs
echo "[*] Installing Python libraries (matplotlib, numpy)..."
sudo apt install -y \
    python3-pip \
    python3-matplotlib \
    python3-numpy \
    python3-psutil

# 4. Verify cgroup v2 support (required for modern BPF maps)
if grep -q cgroup2 /proc/filesystems; then
    echo "[+] cgroup v2 support verified."
else
    echo "[!] WARNING: cgroup v2 support missing. Map pinning may fail."
fi

# 5. Interface Optimization (Host only)
# Automatically fetch the default network interface to suggest optimization
DEFAULT_IF=$(ip route | grep default | awk '{print $5}' | head -n 1)
echo ""
echo "-------------------------------------------------------"
echo "✅ Environment is ready!"
echo ""
echo "Next steps:"
echo "1. Run 'make' to compile the Data Plane."
echo "2. If on Host, disable offloading on your NIC (e.g. $DEFAULT_IF):"
echo "   sudo ethtool -K $DEFAULT_IF sg off tso off gro off gso off"
echo "3. Run the benchmark:"
echo "   sudo python3 scripts/benchmark_runner.py"
echo "-------------------------------------------------------"
