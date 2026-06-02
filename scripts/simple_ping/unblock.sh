#!/bin/bash
# Terminal 3: Unblock 10.0.0.2 using guard.sh

BLUE='\033[0;34m'
GREEN='\033[0;32m'
NC='\033[0m'

echo -e "${BLUE}Unblocking 10.0.0.2...${NC}"
sudo ../../scripts/guard.sh -D -s 10.0.0.2
echo -e "${GREEN}Done.${NC}"
