#!/bin/bash
# SPDX-License-Identifier: GPL-2.0

if [ "$EUID" -ne 0 ]; then
    echo "Error: Run as root."
    exit 1
fi

if [ -z "$1" ] || [[ "$1" == -* ]] || [ -z "$3" ] || [ "$2" != "-i" ]; then
    echo "Usage: $0 <DEST_IP> -i <INTERFACE> [-m <DEST_MAC>]"
    exit 1
fi

DEST_IP=$1
DEV=$3
DST_MAC=$5

# Load kernel module
modprobe pktgen

# Auto-detect MAC if not provided
if [ -z "$DST_MAC" ]; then
    ping -c 1 -W 1 $DEST_IP > /dev/null
    DST_MAC=$(ip neighbor show $DEST_IP | awk '{print $5}' | grep -E '([0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2}')
    [ -z "$DST_MAC" ] && DST_MAC="90:e2:ba:ff:ff:ff"
fi

echo "reset" > /proc/net/pktgen/pgctrl

CPUS=$(nproc)
for ((i=0; i<$CPUS; i++)); do
    T_DEV="${DEV}@${i}"
    echo "rem_device_all" > /proc/net/pktgen/kpktgend_$i
    echo "add_device $T_DEV" > /proc/net/pktgen/kpktgend_$i

    {
        echo "flag QUEUE_MAP_CPU"
        echo "count 0"
        echo "clone_skb 100000"
        echo "pkt_size 60"
        echo "delay 0"
        echo "burst 32"
        echo "flag NO_TIMESTAMP"
        echo "dst_mac $DST_MAC"
        echo "dst $DEST_IP"
        echo "flag UDPSRC_RND"
        echo "udp_src_min 9"
        echo "udp_src_max 109"
    } > /proc/net/pktgen/$T_DEV
done

trap "echo 'Stopping...'; echo 'stop' > /proc/net/pktgen/pgctrl; exit" SIGINT

echo "Starting flood to $DEST_IP via $DEV ($CPUS threads). Press Ctrl+C to stop."
echo "start" > /proc/net/pktgen/pgctrl

wait
