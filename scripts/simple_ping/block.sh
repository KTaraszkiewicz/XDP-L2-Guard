#!/bin/bash
# Terminal 3: Block 10.0.0.2

RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m'

echo -e "${RED}Blocking 10.0.0.2 in XDP map...${NC}"
ip netns exec ns1 bpftool map update name blacklist_ips key hex 0a 00 00 02 value hex 00 00 00 00 00 00 00 00
echo -e "${GREEN}Blocked.${NC}"
