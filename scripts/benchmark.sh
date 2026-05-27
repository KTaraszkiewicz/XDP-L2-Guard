#!/bin/bash

# XDP-L2-Guard Benchmark: XDP vs iptables
# Setup: 3 Namespaces (ns1, ns2, ns3) connected via Bridge
# Scenario: ns3 floods ns1. Measure impact on ns1 <-> ns2 communication.

set -e

# Configuration
BR="br0"
NS1="ns1"; IP1="10.0.0.1"; MAC1="00:00:00:00:00:01"
NS2="ns2"; IP2="10.0.0.2"; MAC2="00:00:00:00:00:02"
NS3="ns3"; IP3="10.0.0.3"; MAC3="00:00:00:00:00:03"
VETH_NS3="veth_ns3_root"

cleanup() {
    echo "🧹 Cleaning up..."
    ip netns del $NS1 2>/dev/null || true
    ip netns del $NS2 2>/dev/null || true
    ip netns del $NS3 2>/dev/null || true
    ip link del $BR 2>/dev/null || true
}

setup_net() {
    echo "🏗️ Setting up Network Namespaces..."
    ip link add $BR type bridge
    ip link set $BR up

    for i in 1 2 3; do
        NS="ns$i"; IP="10.0.0.$i"; MAC="00:00:00:00:00:0$i"
        V_ROOT="veth_ns${i}_root"; V_NS="veth_ns${i}"
        
        ip netns add $NS
        ip link add $V_NS type veth peer name $V_ROOT
        ip link set $V_NS netns $NS
        ip link set $V_ROOT master $BR
        
        ip netns exec $NS ip link set lo up
        ip netns exec $NS ip link set $V_NS address $MAC
        ip netns exec $NS ip link set $V_NS up
        ip netns exec $NS ip addr add $IP/24 dev $V_NS
        
        ip link set $V_ROOT up
    done
}

run_test() {
    MODE=$1 # "iptables" or "xdp"
    echo "🚀 Running Benchmark: $MODE"
    
    # Reset
    iptables -F
    # TODO: Detach XDP
    
    if [ "$MODE" == "iptables" ]; then
        echo "🛡️ Setting up iptables drop rule..."
        # Drop packets from ns3 MAC at the bridge/root level
        iptables -A FORWARD -m mac --mac-source $MAC3 -j DROP
    else
        echo "🛡️ Loading XDP-L2-Guard..."
        # TODO: Command to load XDP on $VETH_NS3
        # sudo python3 src/control_plane/loader.py --iface $VETH_NS3 --blacklist $MAC3
        sleep 2
    fi

    # Start iperf server in ns1
    ip netns exec $NS1 iperf3 -s -D
    sleep 1

    echo "🔥 Starting Flood from $NS3..."
    ip netns exec $NS3 hping3 --flood --udp -a $IP3 $IP1 >/dev/null 2>&1 &
    FLOOD_PID=$!

    echo "📊 Measuring Throughput (ns2 -> ns1)..."
    RESULT=$(ip netns exec $NS2 iperf3 -c $IP1 -t 10 --json)
    THROUGHPUT=$(echo $RESULT | jq '.end.sum_received.bits_per_second / 1000000')
    
    echo "📊 Measuring Latency (ns2 -> ns1)..."
    LATENCY=$(ip netns exec $NS2 ping $IP1 -c 10 -q | awk -F '/' 'END {print $5}')

    kill $FLOOD_PID || true
    pkill iperf3 || true
    
    echo "RESULT:$MODE:$THROUGHPUT:$LATENCY" >> bench_results.csv
}

cleanup
setup_net
echo "Mode:Throughput(Mbps):Latency(ms)" > bench_results.csv
run_test "iptables"
# run_test "xdp" # Enable after XDP loader ready

echo "✅ Benchmark Complete."
cat bench_results.csv

# TODO: Add gnuplot script to generate PNG
