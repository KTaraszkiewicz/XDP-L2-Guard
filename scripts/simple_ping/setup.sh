#!/bin/bash
# Terminal 1: Setup Environment
set -e

GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

NS1="ns1"
NS2="ns2"
BPF_OBJ="../../src/data_plane/filter.o"

cleanup() {
    ip netns del $NS1 2>/dev/null || true
    ip netns del $NS2 2>/dev/null || true
}
trap cleanup EXIT

echo -e "${BLUE}Setting up namespaces and XDP...${NC}"
ip netns add $NS1
ip netns add $NS2
ip link add veth-ns1 type veth peer name veth-ns2
ip link set veth-ns1 netns $NS1
ip link set veth-ns2 netns $NS2

ip netns exec $NS1 ip addr add 10.0.0.1/24 dev veth-ns1
ip netns exec $NS1 ip link set veth-ns1 up
ip netns exec $NS1 ip link set lo up

ip netns exec $NS2 ip addr add 10.0.0.2/24 dev veth-ns2
ip netns exec $NS2 ip link set veth-ns2 up
ip netns exec $NS2 ip link set lo up

echo -e "${BLUE}Loading XDP (Native/Driver mode)...${NC}"
ip netns exec $NS1 ip link set dev veth-ns1 xdpdrv obj $BPF_OBJ sec xdp

echo -e "${GREEN}Environment Ready.${NC}"
echo "Keep this open. Press Ctrl+C to exit."
while true; do sleep 1; done
