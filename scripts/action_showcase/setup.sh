#!/bin/bash
# Terminal 1: Setup Action Showcase (3 Namespaces)
set -e

GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

NS1="ns1"
NS2="ns2"
NS3="ns3"
BPF_OBJ="/home/jos/XDP-L2-Guard/src/data_plane/filter.o"

cleanup() {
    ip netns del $NS1 2>/dev/null || true
    ip netns del $NS2 2>/dev/null || true
    ip netns del $NS3 2>/dev/null || true
}
trap cleanup EXIT

echo -e "${BLUE}Setting up 3-node network (ns1, ns2, ns3)...${NC}"
ip netns add $NS1
ip netns add $NS2
ip netns add $NS3

# Bridge-like setup in ns1 using veth pairs
# ns1 <-> ns2
ip link add v1-2 type veth peer name v2-1
ip link set v1-2 netns $NS1
ip link set v2-1 netns $NS2

# ns1 <-> ns3
ip link add v1-3 type veth peer name v3-1
ip link set v1-3 netns $NS1
ip link set v3-1 netns $NS3

# Config IPs
ip netns exec $NS1 ip addr add 10.0.0.1/24 dev v1-2
ip netns exec $NS1 ip link set v1-2 up
ip netns exec $NS1 ip link set v1-3 up
ip netns exec $NS1 ip link set lo up

ip netns exec $NS2 ip addr add 10.0.0.2/24 dev v2-1
ip netns exec $NS2 ip link set v2-1 up
ip netns exec $NS2 ip link set lo up

ip netns exec $NS3 ip addr add 10.0.0.3/24 dev v3-1
ip netns exec $NS3 ip link set v3-1 up
ip netns exec $NS3 ip link set lo up

# Enable forwarding in ns1 for NAT/Redirect tests
ip netns exec $NS1 sysctl -w net.ipv4.ip_forward=1 >/dev/null

echo -e "${BLUE}Loading XDP on ns1 (v1-2 and v1-3)...${NC}"
ip netns exec $NS1 ip link set dev v1-2 xdpgeneric obj $BPF_OBJ sec xdp
ip netns exec $NS1 ip link set dev v1-3 xdpgeneric obj $BPF_OBJ sec xdp

echo -e "${GREEN}Action Showcase Ready.${NC}"
echo "------------------------------------------------"
echo "ns1 (Filter): 10.0.0.1 | v1-2 (XDP)"
echo "ns2 (Sender): 10.0.0.2"
echo "ns3 (Target): 10.0.0.3"
echo "------------------------------------------------"
echo "Keep this open. Use set_action.sh in other terminal."
while true; do sleep 1; done
