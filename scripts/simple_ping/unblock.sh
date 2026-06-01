#!/bin/bash
# Terminal 3: Unblock 10.0.0.2

BLUE='\033[0;34m'
GREEN='\033[0;32m'
NC='\033[0m'

echo -e "${BLUE}Unblocking 10.0.0.2...${NC}"
ip netns exec ns1 bpftool map delete name blacklist_ips key hex 0a 00 00 02
echo -e "${GREEN}Unblocked.${NC}"
