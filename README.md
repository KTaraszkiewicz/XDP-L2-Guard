# XDP-L2-Guard 🛡️🚀

[![Kernel Compatibility](https://img.shields.io/badge/Kernel-5.15%2B-blue.svg)](https://kernel.org)
[![Platform](https://img.shields.io/badge/Platform-Ubuntu%2022.04%20LTS-orange.svg)](https://ubuntu.com)
[![Technology](https://img.shields.io/badge/Technology-eBPF%20%2F%20XDP%20Native-flash.svg)](https://ebpf.io)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

An advanced, high-performance Layer 2 frame filtering engine built upon **eBPF** (extended Berkeley Packet Filter) and **XDP** (eXpress Data Path).

By dropping packets at the network interface driver level—completely bypassing expensive Linux network stack `sk_buff` allocations—XDP-L2-Guard provides real-time volumetric DDoS mitigation that easily handles line-rate saturation without exhausting system resources.

## Features

- **Microsecond Latency**: Acts directly on the NIC's DMA ring buffer.
- **Negligible CPU Overhead**: Reduces CPU utilization to ~15% under floods that completely paralyze standard Netfilter (`iptables`).
- **Rich Action Set**: Beyond dropping, supports `PASS`, `TX` (fast-path bounce), `NAT` (stateless rewriting), and `REDIRECT` (L2 forwarding).
- **Familiar CLI**: `guard.py` offers an `iptables`-like syntax for adding and removing mitigation rules dynamically.
- **CO-RE Architecture**: Modern "Compile Once - Run Everywhere" AOT deployment.

## Installation

**Requirements:** Ubuntu 22.04 LTS (or newer) running Linux Kernel `5.15.0` or higher.

1. Clone the repository and navigate to the root directory.
2. Provision the execution environment (installs `clang`, `llvm`, `libbpf-dev`, etc.):

```bash
./scripts/setup_env.sh
```

> [!IMPORTANT]  
> If you are using native XDP hardware offload, hardware segmentation features like GRO and TSO must be suppressed to keep packet sizes within BPF page limits:
>
> ```bash
> sudo ethtool -K eth0 sg off tso off ufo off gro off gso off
> ```

## Quickstart

Start the core XDP loader and attach the data-plane to your network interface. For demonstration, we'll use `eth0`:

```bash
# Start the XDP orchestrator (use --generic for testing environments like VMs)
sudo python3 src/control_plane/loader.py --interface eth0
```

With the engine running, open another terminal and use `guard.py` to mitigate threats.

### Adding a rule (Drop IP)
```bash
sudo python3 src/control_plane/guard.py -A -d 192.168.1.100 -j DROP
```

### Checking statistics
```bash
sudo python3 src/control_plane/guard.py -L
```

### Removing a rule
```bash
sudo python3 src/control_plane/guard.py -D -d 192.168.1.100
```

## Advanced Actions

XDP-L2-Guard supports forwarding actions alongside standard filtering.

### Stateless NAT
Rewrite destination IP for incoming packets to a new address:
```bash
sudo python3 src/control_plane/guard.py -A -d 10.0.0.50 -j NAT --to-destination 10.0.0.200
```

### Fast-path Redirect
Push incoming traffic matching an IP immediately out of a different interface (e.g., `eth1`):
```bash
sudo python3 src/control_plane/guard.py -A -d 10.0.0.60 -j REDIRECT --oif eth1
```

## Architecture

XDP-L2-Guard employs a decoupled split-plane model. For more details, see the [Architecture Overview](docs/architecture.md) and the [Developer Guide](docs/development.md).

- **Data Plane (Kernel Space):** Highly restrictive, boundary-checked C code hooks into the NIC's NAPI driver loop.
- **Control Plane (User Space):** Python orchestration binds the pre-compiled CO-RE eBPF binaries to the interface via `iproute2` and interacts asynchronously via BPF maps.

<details>
<summary>View repository structure</summary>

```text
xdp-l2-guard/
├── src/
│   ├── data_plane/         # Kernel Space (eBPF C code)
│   └── control_plane/      # User Space (loader & CLI orchestrator)
├── scripts/                # Setup and traffic generation tools
├── docs/                   # Technical documentation
├── lkm_panic/              # LKM crash simulation demo
├── Makefile                # CO-RE compilation directives
└── LICENSE                 # MIT License
```

</details>

## Authors

Developers: Krzysztof Taraszkiewicz and Józef Sztabiński  
Academic Supervisor: dr inż Jerzy Demkowicz  
Developed as part of the Advanced Computer Architecture miniProject at Gdańsk University of Technology.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
