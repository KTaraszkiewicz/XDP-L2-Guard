# Hardware Test Setup

## SENDER MACHINE (10.0.1.10)
```bash
# Set IP & Up
sudo ip addr add 10.0.1.10/24 dev eth0
sudo ip link set eth0 up

# Start Flood (UDP, 64B, 4 cores)
sudo hping3 --flood --udp -d 64 -a 10.0.1.10 10.0.1.1
```

## HOST MACHINE (10.0.1.1)
```bash
# Load XDP Native
sudo python3 src/control_plane/loader.py -i eth0

# Block Dest IP (local)
sudo python3 src/control_plane/guard.py -A -d 10.0.1.1 -j DROP

# Plot Results
python3 scripts/plot_hw_results.py
```
