#!/bin/bash
# Terminal 3: Block 10.0.0.2 using guard.sh

RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m'

echo -e "${RED}Blocking 10.0.0.2...${NC}"
sudo ../../scripts/guard.sh -A -s 10.0.0.2 -j DROP
echo -e "${GREEN}Done.${NC}"
