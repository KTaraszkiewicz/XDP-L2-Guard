#!/bin/bash
# Terminal 2: Continuous Ping

BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}Pinging 10.0.0.2 from ns1...${NC}"
ip netns exec ns1 ping 10.0.0.2
