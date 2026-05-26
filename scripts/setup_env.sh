#!/bin/bash

# Exit immediately if a command exits with a non-zero status
set -e

echo "🚀 Starting XDP-L2-Guard environment configuration (CO-RE Standard)..."

# 1. Verify kernel version (5.15+ required)
KERNEL_VERSION=$(uname -r)
echo "🛡️ Detected kernel version: $KERNEL_VERSION"

# 2. Update repositories and install base packages
echo "📦 Installing base packages, compilers, and system tools..."
# Required LLVM/Clang tools, kernel headers for AOT compilation, and linux-tools for bpftool
sudo apt update && sudo apt install -y \
    clang \
    llvm \
    libbpf-dev \
    linux-headers-$(uname -r) \
    linux-tools-common \
    linux-tools-$(uname -r) \
    ethtool \
    net-tools \
    gcc \
    make

# 3. Verify cgroup v2 support (required by modern eBPF maps)
if grep -q cgroup2 /proc/filesystems; then
    echo "✅ cgroup v2 support verified."
else
    echo "⚠️ WARNING: cgroup v2 support missing, please check kernel configuration!"
fi

# 4. Optimize interface for XDP Native (Disable hardware offloading)
# Automatically fetch the default network interface
INTERFACE=$(ip route | grep default | awk '{print $5}' | head -n 1)

echo "🔧 Configuring network interface: $INTERFACE"
echo "Disabling hardware offloading (GRO, GSO, SG, TSO) to prevent frame segmentation conflicts..."
# Disable hardware assistance to redirect raw packets directly to the native eBPF loop
sudo ethtool -K $INTERFACE sg off tso off ufo off gro off gso off || echo "Note: Some ethtool options might not be supported by the virtual network adapter."

echo "🎉 Environment is ready! You can now compile the code using 'make' and launch the orchestrator."