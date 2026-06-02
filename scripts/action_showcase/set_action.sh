#!/bin/bash
# Terminal 2: Configure Actions using guard.sh

RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

if [ -z "$1" ]; then
    echo "Usage: $0 <pass|drop|tx|redirect|nat>"
    exit 1
fi

ACTION=$1
GUARD="../../scripts/guard.sh"

case ${ACTION,,} in
    pass)
        sudo $GUARD -A -s 10.0.0.2 -j PASS
        ;;
    drop)
        sudo $GUARD -A -s 10.0.0.2 -j DROP
        ;;
    tx)
        sudo $GUARD -A -s 10.0.0.2 -j TX
        ;;
    redirect)
        sudo $GUARD -A -s 10.0.0.2 -j REDIRECT --oif v1-3
        ;;
    nat)
        sudo $GUARD -A -s 10.0.0.2 -j NAT --to-destination 10.0.0.3
        ;;
    *)
        echo "Invalid action"
        exit 1
        ;;
esac
