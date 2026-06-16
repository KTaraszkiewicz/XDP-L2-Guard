# XDP-L2-Guard Demonstration Environment

This directory contains a self-contained demonstration environment using Linux Network Namespaces (`netns`). It simulates a 3-node network to showcase XDP packet filtering, forwarding, and real-time telemetry without needing physical hardware or complex VM setups.

## Overview

The environment creates three namespaces connected via `veth` pairs:
* **ns1 (Filter / Router):** `10.0.0.1` - The node running the XDP program.
* **ns2 (Sender):** `10.0.0.2` - The source of traffic.
* **ns3 (Target):** `10.0.0.3` - The destination for traffic.

## Installation

No extra installation required beyond the main project. Ensure `clang` and `llvm` are installed via `../setup_env.sh` and run `make` in the project root.

To fully experience the XDP capabilities, open 5 separate terminal windows.

### Terminal 1: Network & XDP Setup

Recompile the XDP program and launch the network namespace environment. This script will block and keep the network alive.

```bash
# From project root
make clean && make
sudo ./scripts/example/setup.sh
```

### Terminal 2: Packet Monitor (tcpdump)

Watch the ICMP traffic arriving at the Sender (`ns2`) and Target (`ns3`) in real-time.

```bash
sudo ./scripts/example/monitor.sh
```

### Terminal 3: Real-time Telemetry

Launch the new eBPF map telemetry monitor. This dashboard displays live packet counts per source IP as tracked directly inside the XDP data plane.

```bash
# From project root
sudo ./src/control_plane/telemetry.py
```

### Terminal 4: Generate Traffic

Start a continuous ping from the Sender (`ns2`) to the Filter node (`ns1`). You can edit this script to ping `ns3` (`10.0.0.3`) as well.

```bash
sudo ./scripts/example/ping.sh
```

### Terminal 5: Control Plane (Rule Management)

With traffic flowing (Terminal 4) and monitors watching (Terminals 2 & 3), use the control plane to dynamically change how the XDP program handles the packets.

> [!NOTE]  
> All control plane commands must be run from the project root.

**1. Drop Traffic**
```bash
sudo python3 src/control_plane/guard.py -A -d 10.0.0.1 -j DROP
```
*Observe:* `ping.sh` stops receiving replies. `telemetry.py` shows packet counts increasing as packets are intercepted and tracked by XDP.

**2. Fast-Path Bounce (TX)**
```bash
sudo python3 src/control_plane/guard.py -A -d 10.0.0.1 -j TX
```
*Observe:* `ping.sh` receives replies again, but they are bounced directly from the XDP layer, bypassing the kernel network stack entirely.

**3. Redirect to Target (ns3)**
```bash
sudo python3 src/control_plane/guard.py -A -d 10.0.0.1 -j REDIRECT --oif v1-3
```
*Observe:* Traffic intended for `10.0.0.1` is instantly redirected out the `v1-3` interface. `monitor.sh` will show the packets arriving at `ns3`.

**4. Remove Rules**
```bash
sudo python3 src/control_plane/guard.py -D -d 10.0.0.1
```
*Observe:* Behavior returns to standard kernel network stack routing.
