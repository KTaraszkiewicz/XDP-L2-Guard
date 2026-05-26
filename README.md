# XDP-L2-Guard 🛡️🚀

[![Kernel Compatibility](https://img.shields.io/badge/Kernel-5.15%2B-blue.svg)](https://kernel.org)
[![Platform](https://img.shields.io/badge/Platform-Ubuntu%2022.04%20LTS-orange.svg)](https://ubuntu.com)
[![Technology](https://img.shields.io/badge/Technology-eBPF%20%2F%20XDP%20Native-flash.svg)](https://ebpf.io)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

An advanced, high-performance Layer 2 frame filtering engine built upon **eBPF (extended Berkeley Packet Filter)** and **XDP (eXpress Data Path)**. This project implements a split-plane architecture designed for real-time volumetric DDoS mitigation at the network interface driver level, completely bypassing the expensive Linux network stack allocation overhead.

---

## 📁 Repository Structure

```text
xdp-l2-guard/
├── src/
│   ├── data_plane/         # Kernel Space: eBPF C source code
│   │   ├── filter.c        # Core XDP packet processing and dropping logic
│   │   └── headers.h       # Protocol structures and verifier boundary helpers
│   └── control_plane/      # User Space: Orchestration & Monitoring
│       ├── loader.py       # Python BCC script (JIT compilation & interface binding)
│       └── utils.py        # Helper routines and logging configuration
├── scripts/
│   ├── setup_env.sh        # Automated toolchain provisioning script
│   └── benchmark.sh        # Traffic generation wrapper (pktgen / hping3)
├── lkm_panic/              # Demo: Linux Kernel Module (LKM) crash simulation
│   ├── Makefile            # Build directives to compile the malicious kernel object (.ko)
│   └── null_pointer.c      # Vulnerable C code triggering intentional NULL pointer dereference
├── docs/
│   └── documentation.md    # Detailed technical documentation & edge cases analysis
├── README.md               # Project overview and deployment guide
└── LICENSE                 # Project license
```

---

## 🏗️ Architectural Overview

The system architecture is divided into two decoupled operations planes communicating asynchronously via high-performance **eBPF Maps**:

1. **Data Plane (Kernel Space):** Written in *Restrictive C*, hooked directly into the network interface card (NIC) driver event loop (NAPI). It performs line-rate parsing, boundary-checked pointer arithmetic, and issues instantaneous `XDP_DROP` verdicts.
2. **Control Plane (User Space):** Written in *Python* utilizing the **BCC (BPF Compiler Collection)** framework. It triggers JIT compilation, attaches/detaches eBPF bytecode, subscribes to asynchronous asynchronous asynchronous kernel Netlink events, and polls metrics from shared BPF Hash maps.

---

## 📊 Performance Benchmarks (XDP Native vs. Netfilter iptables)

During exhaustive stress-testing under massive volumetric network anomalies (e.g., TCP SYN flood/ICMP streams via `pktgen` and `hping3`), the following paradigm shift was observed:

| Performance Metric | Traditional `iptables` (Netfilter) | `XDP-L2-Guard` (XDP Native) |
| :--- | :--- | :--- |
| **Packet Processing Hook** | Late (Post-`sk_buff` allocation in Kernel Stack) | Ultra-Early (Direct DMA Ring Buffer / Driver Level) |
| **CPU Utilization** | **100%** (CPU saturated by `ksoftirqd` software interrupts) | **~15%** (Negligible impact on host compute resources) |
| **Drop Throughput (Single Core)** | Ring Buffer Saturation (~9M packets overwritten/lost) | **>26 Million Packets Per Second (PPS)** stable |
| **System Latency** | Massive jitter / complete network paralysis | Zero-latency tolerance (Sub-millisecond ping response) |

---

## 🛠️ Environment Requirements & Toolchain

To replicate the environment and ensure compatibility with advanced BPF helpers, the host runtime must meet the following baseline configuration:

* **Operating System:** Ubuntu 22.04 LTS (or newer)
* **Kernel Version:** `5.15.0` or higher (Full BPF verifier optimization and modern map-type support)
* **Base Packages:** `libbpf`, `bcc` (BPF Compiler Collection)
* **Compiler Toolchain:** `clang`, `llvm`, `libbpf-dev`, `linux-headers-$(uname -r)`
* **Network Infrastructure:** Active `Ethernet Carrier` state, utilizing `virtio_net` (QEMU/KVM) or paired `veth` interfaces supporting Native XDP mode (`xdpdrv`).

---

## 🚀 Quick Start & Deployment Guide

### 1. Provisioning the Toolchain
Deploy the execution environment dependencies via the provided provisioning automation script:
```bash
sudo apt update && sudo apt install -y clang llvm libbpf-dev bcc-tools libbcc-dev linux-headers-$(uname -r) python3-bcc
```
### 2. Mitigating Hardware Offload Incompatibilities
Before mounting the native data plane, hardware features such as GRO (Generic Receive Offload) must be explicitly suppressed to prevent MTU segmentation anomalies outside BPF page restrictions:
```bash
sudo ethtool -K eth0 gro off gso off tx off rx off
```
### (Automated option) 1. and 2. are composed into script setup_env.sh:
```bash
./setup_env.sh
```

### 3. Launching the Security Engine
Execute the control plane loader script to compile and attach the high-speed data plane filters onto the designated hardware interface:
```bash
sudo python3 src/control_plane/loader.py --interface eth0
```
To run the engine in simulated Generic mode (for testing inside limited containers or non-native drivers), use the --generic flag:
```bash
sudo python3 src/control_plane/loader.py --interface eth0 --generic
```
---

## 🛡️ Dynamic Blacklist Configuration

The engine uses an in-kernel BPF Hash Map (blacklist_ips) to store targets. You can interact with the live kernel data plane directly from User Space using standard toolsets.
- Manually insert a blocked IPv4 address (e.g., 192.168.1.100 -> Hex: c0 a8 01 64):
  ```bash
  sudo bpftool map update name blacklist_ips key 0xc0 0xa8 0x01 0x64 value 0x00 0x00 0x00 0x00
  ```
- Inspect current drops and counters:
  ```bash
  sudo bpftool map dump name blacklist_ips
  ```
---
  
## 👥 Authors & Acknowledgments

Developers: Krzysztof Taraszkiewicz and Józef Sztabiński  
Academic Supervisor: dr inż Jerzy Demkowicz  
Developed as part of Advanced Computer Architecture miniProject at Gdańsk University of Technology (Politechnika Gdańska).

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
