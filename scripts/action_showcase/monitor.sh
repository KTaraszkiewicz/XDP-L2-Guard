#!/bin/bash
# Terminal 3: Monitor Traffic

BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${BLUE}Starting monitors...${NC}"
echo "------------------------------------------------"

# Monitor ns2 (Sender)
ip netns exec ns2 tcpdump -l -n -i v2-1 icmp 2>/dev/null | sed "s/^/[NS2] /" &
PID_NS2=$!

# Monitor ns3 (Target)
ip netns exec ns3 tcpdump -l -n -i v3-1 icmp 2>/dev/null | sed "s/^/[NS3] /" &
PID_NS3=$!

echo "Watching [NS2] and [NS3]. Press Ctrl+C to stop."

trap "kill $PID_NS2 $PID_NS3" EXIT
wait
