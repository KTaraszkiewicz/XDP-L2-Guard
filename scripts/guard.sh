#!/bin/bash

# XDP Guard CLI - Bash Version
# Style: iptables-like

RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

# Action targets
ACTION_PASS=0
ACTION_DROP=1
ACTION_TX=2
ACTION_REDIRECT=3
ACTION_NAT=4

# Helper: IP to Hex (Network Byte Order for key)
ip_to_hex() {
    local ip=$1
    IFS=. read -r a b c d <<< "$ip"
    printf "%02x %02x %02x %02x" "$a" "$b" "$c" "$d"
}

# Helper: Pack 4-byte Little Endian Hex (for struct values)
pack_u32() {
    local n=$1
    printf "%08x" "$n" | sed 's/\(..\)\(..\)\(..\)\(..\)/\4 \3 \2 \1/'
}

# Find Map IDs
ACT_MAP_IDS=$(bpftool map list 2>/dev/null | grep action_map | awk -F: '{print $1}')
DEV_MAP_IDS=$(bpftool map list 2>/dev/null | grep dev_map | awk -F: '{print $1}')

# Pick one for listing (first one with elements, or just first one)
ACT_MAP_ID_LIST=""
for id in $ACT_MAP_IDS; do
    [ -z "$ACT_MAP_ID_LIST" ] && ACT_MAP_ID_LIST=$id
    if bpftool --json map dump id "$id" | jq -e 'length > 0' >/dev/null 2>&1; then
        ACT_MAP_ID_LIST=$id
        break
    fi
done

usage() {
    echo "Usage: $0 [options]"
    echo "  -A, --append         Add a rule"
    echo "  -D, --delete         Delete a rule"
    echo "  -L, --list           List rules"
    echo "  -s, --source IP      Source IP address"
    echo "  -j, --jump TARGET    Target: PASS, DROP, TX, REDIRECT, NAT"
    echo "  --to-destination IP  NAT target IP"
    echo "  --oif IFACE          Redirect interface"
    exit 1
}

# Parse Args
while [[ $# -gt 0 ]]; do
    case $1 in
        -A|--append) MODE="ADD"; shift ;;
        -D|--delete) MODE="DEL"; shift ;;
        -L|--list)   MODE="LIST"; shift ;;
        -s|--source) SRC_IP="$2"; shift 2 ;;
        -j|--jump)   TARGET="$2"; shift 2 ;;
        --to-destination) NAT_IP="$2"; shift 2 ;;
        --oif)       OIF="$2"; shift 2 ;;
        *) usage ;;
    esac
done

if [ -z "$ACT_MAP_IDS" ]; then
    echo -e "${RED}Error: XDP maps not found. Is loader running?${NC}"
    exit 1
fi

if [ "$MODE" == "LIST" ]; then
    echo -e "${BLUE}SOURCE IP       | ACTION     | DETAILS${NC}"
    echo "------------------------------------------------"

    [ -z "$ACT_MAP_ID_LIST" ] && exit 0

    # Use JSON output for reliable parsing
    bpftool --json map dump id "$ACT_MAP_ID_LIST" | jq -r '.[] | .formatted | [.key, .value.target, .value.new_ip, .value.ifindex] | @tsv' 2>/dev/null | while IFS=$'\t' read -r key target new_ip ifindex; do
        # Convert decimal IP (Little Endian from map) to dotted string
        ip=$(printf "%d.%d.%d.%d" $((key & 0xFF)) $(((key >> 8) & 0xFF)) $(((key >> 16) & 0xFF)) $(((key >> 24) & 0xFF)))

        actions=("PASS" "DROP" "TX" "REDIRECT" "NAT")
        act_str=${actions[$target]}
        details=""
        if [ "$target" -eq "$ACTION_NAT" ]; then
            nip=$(printf "%d.%d.%d.%d" $((new_ip & 0xFF)) $(((new_ip >> 8) & 0xFF)) $(((new_ip >> 16) & 0xFF)) $(((new_ip >> 24) & 0xFF)))
            details="to $nip"
        elif [ "$target" -eq "$ACTION_REDIRECT" ]; then
            details="to ifindex $ifindex"
        fi
        
        printf "%-15s | %-10s | %s\n" "$ip" "$act_str" "$details"
    done
    exit 0
fi

if [ "$MODE" == "ADD" ]; then
    [ -z "$SRC_IP" ] || [ -z "$TARGET" ] && usage
    
    T_VAL=0
    NAT_HEX="00 00 00 00"
    OIF_HEX="00 00 00 00"

    case ${TARGET^^} in
        PASS) T_VAL=$ACTION_PASS ;;
        DROP) T_VAL=$ACTION_DROP ;;
        TX)   T_VAL=$ACTION_TX ;;
        REDIRECT) 
            T_VAL=$ACTION_REDIRECT 
            [ -z "$OIF" ] && echo "Error: --oif required" && exit 1
            
            # Optional NAT in redirect
            if [ -n "$NAT_IP" ]; then
                NAT_HEX=$(ip_to_hex "$NAT_IP")
            fi
            
            # Find ifindex and the namespace it belongs to
            OIF_IDX=$(ip -o link show dev "$OIF" 2>/dev/null | awk -F': ' '{print $1}')
            OIF_NS=""
            
            if [ -z "$OIF_IDX" ]; then
                for ns in $(ip netns list 2>/dev/null | awk '{print $1}'); do
                    OIF_IDX=$(ip netns exec "$ns" ip -o link show dev "$OIF" 2>/dev/null | awk -F': ' '{print $1}')
                    if [ -n "$OIF_IDX" ]; then
                        OIF_NS="$ns"
                        break
                    fi
                done
            fi
            
            [ -z "$OIF_IDX" ] && echo "Error: Interface $OIF not found" && exit 1
            OIF_HEX=$(pack_u32 "$OIF_IDX")
            
            # Update all dev_maps
            for id in $DEV_MAP_IDS; do
                if [ -n "$OIF_NS" ]; then
                    ip netns exec "$OIF_NS" bpftool map update id "$id" key hex $OIF_HEX value hex $OIF_HEX 2>/dev/null
                else
                    bpftool map update id "$id" key hex $OIF_HEX value hex $OIF_HEX 2>/dev/null
                fi
            done
            ;;
        NAT)
            T_VAL=$ACTION_NAT
            [ -z "$NAT_IP" ] && echo "Error: --to-destination required" && exit 1
            NAT_HEX=$(ip_to_hex "$NAT_IP")
            ;;
    esac

    SRC_HEX=$(ip_to_hex "$SRC_IP")
    T_HEX=$(pack_u32 "$T_VAL")
    VAL_HEX="$T_HEX $NAT_HEX $OIF_HEX"

    SUCCESS=0
    for id in $ACT_MAP_IDS; do
        if bpftool map update id "$id" key hex $SRC_HEX value hex $VAL_HEX; then
            SUCCESS=1
        fi
    done

    if [ "$SUCCESS" -eq 1 ]; then
        echo -e "${GREEN}Rule added: $SRC_IP -> $TARGET${NC}"
    else
        echo -e "${RED}Error: Failed to update map.${NC}"
    fi

elif [ "$MODE" == "DEL" ]; then
    [ -z "$SRC_IP" ] && usage
    SUCCESS=0
    for id in $ACT_MAP_IDS; do
        if bpftool map delete id "$id" key hex $(ip_to_hex "$SRC_IP"); then
            SUCCESS=1
        fi
    done
    if [ "$SUCCESS" -eq 1 ]; then
        echo -e "${GREEN}Rule deleted for $SRC_IP${NC}"
    else
        echo -e "${RED}Error: Failed to delete rule.${NC}"
    fi
else
    usage
fi
