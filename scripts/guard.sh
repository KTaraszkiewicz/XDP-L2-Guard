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

# Helper: IP to Hex (Big Endian)
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

usage() {
    echo "Usage: $0 [options]"
    echo "  -A, --append         Add a rule"
    echo "  -D, --delete         Delete a rule"
    echo "  -L, --list           List rules"
    echo "  -d, --destination IP Destination IP address"
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
        -d|--destination) DST_IP="$2"; shift 2 ;;
        -s|--source)      DST_IP="$2"; shift 2 ;; # Backward compat
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
    echo -e "${BLUE}DEST IP         | ACTION     | DROPPED    | DETAILS${NC}"
    echo "---------------------------------------------------------"
    
    # Pick first map for listing
    ACT_MAP_ID=$(echo $ACT_MAP_IDS | awk '{print $1}')
    
    bpftool map dump id "$ACT_MAP_ID" | grep -v "\[" | grep -v "\]" | while read -r line; do
        if [[ $line == *"key:"* ]]; then
            # key is Big Endian IP
            key=$(echo "$line" | cut -d: -f2- | tr -d ' ,')
            ip=$(printf "%d.%d.%d.%d" 0x${key:0:2} 0x${key:2:2} 0x${key:4:2} 0x${key:6:2})
            
            read -r next_line
            # value: target(4), nip(4), idx(4), pad(4), count(8)
            val=$(echo "$next_line" | cut -d: -f2- | tr -d ' ,')
            
            t_hex=${val:0:8}
            t_val=$(( 16#${t_hex:6:2}${t_hex:4:2}${t_hex:2:2}${t_hex:0:2} ))
            
            c_hex=${val:32:16}
            c_val=$(( 16#${c_hex:14:2}${c_hex:12:2}${c_hex:10:2}${c_hex:8:2}${c_hex:6:2}${c_hex:4:2}${c_hex:2:2}${c_hex:0:2} ))

            actions=("PASS" "DROP" "TX" "REDIRECT" "NAT")
            act_str=${actions[$t_val]}
            
            details=""
            if [ "$t_val" -eq "$ACTION_NAT" ]; then
                n_hex=${val:8:8}
                nip=$(printf "%d.%d.%d.%d" 0x${n_hex:0:2} 0x${n_hex:2:2} 0x${n_hex:4:2} 0x${n_hex:6:2})
                details="to $nip"
            elif [ "$t_val" -eq "$ACTION_REDIRECT" ]; then
                i_hex=${val:16:8}
                idx=$(( 16#${i_hex:6:2}${i_hex:4:2}${i_hex:2:2}${i_hex:0:2} ))
                details="to ifindex $idx"
            fi
            
            printf "%-15s | %-10s | %-10s | %s\n" "$ip" "$act_str" "$c_val" "$details"
        fi
    done
    exit 0
fi

if [ "$MODE" == "ADD" ]; then
    [ -z "$DST_IP" ] || [ -z "$TARGET" ] && usage
    
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
            OIF_IDX=$(ip -o link show dev "$OIF" 2>/dev/null | awk -F': ' '{print $1}')
            [ -z "$OIF_IDX" ] && echo "Error: Interface $OIF not found" && exit 1
            OIF_HEX=$(pack_u32 "$OIF_IDX")
            
            for id in $DEV_MAP_IDS; do
                bpftool map update id "$id" key hex $OIF_HEX value hex $OIF_HEX 2>/dev/null
            done
            ;;
        NAT)
            T_VAL=$ACTION_NAT
            [ -z "$NAT_IP" ] && echo "Error: --to-destination required" && exit 1
            NAT_HEX=$(ip_to_hex "$NAT_IP")
            ;;
    esac

    DST_HEX=$(ip_to_hex "$DST_IP")
    T_HEX=$(pack_u32 "$T_VAL")
    PAD_HEX="00 00 00 00"
    CNT_HEX="00 00 00 00 00 00 00 00"
    VAL_HEX="$T_HEX $NAT_HEX $OIF_HEX $PAD_HEX $CNT_HEX"

    SUCCESS=0
    for id in $ACT_MAP_IDS; do
        if bpftool map update id "$id" key hex $DST_HEX value hex $VAL_HEX; then
            SUCCESS=1
        fi
    done

    if [ "$SUCCESS" -eq 1 ]; then
        echo -e "${GREEN}Rule added: $DST_IP -> $TARGET${NC}"
    else
        echo -e "${RED}Error: Failed to update map.${NC}"
    fi

elif [ "$MODE" == "DEL" ]; then
    [ -z "$DST_IP" ] && usage
    SUCCESS=0
    for id in $ACT_MAP_IDS; do
        if bpftool map delete id "$id" key hex $(ip_to_hex "$DST_IP"); then
            SUCCESS=1
        fi
    done
    if [ "$SUCCESS" -eq 1 ]; then
        echo -e "${GREEN}Rule deleted for $DST_IP${NC}"
    else
        echo -e "${RED}Error: Failed to delete rule.${NC}"
    fi
else
    usage
fi
