#!/bin/bash
# SPDX-License-Identifier: GPL-2.0
#
# Zoptymalizowany pod maksymalny PPS dla testów porównawczych XDP vs nftables/iptables
# Automatycznie wykorzystuje wszystkie dostępne rdzenie logiczne procesora.

# --- POMOCNICZE FUNKCJE (zamiast brakujących functions.sh) ---
function pg_ctrl() {
    echo "$1" > /proc/net/pktgen/pgctrl
}

function pg_thread() {
    echo "$2 $3" > /proc/net/pktgen/kpktgend_$1
}

function pg_set() {
    echo "$2" > /proc/net/pktgen/$1
}

function root_check() {
    if [ "$EUID" -ne 0 ]; then
        echo "Błąd: Uruchom skrypt z uprawnieniami root (sudo)."
        exit 1
    fi
}
# -----------------------------------------------------------

root_check

# 1. Logika pobierania argumentów
if [ -z "$1" ] || [[ "$1" == -* ]]; then
    echo "Błąd: Brak docelowego adresu IP."
    echo "Użycie: $0 <Adres_IP_Celu> -i <Interfejs_sieciowy>"
    echo "Przykład: $0 192.168.1.50 -i enp3s0"
    exit 1
fi

DEST_IP=$1
shift

# Parsowanie pozostałych argumentów (np. -i)
while getopts "i:m:" opt; do
    case ${opt} in
        i ) DEV=$OPTARG ;;
        m ) DST_MAC=$OPTARG ;;
    esac
done

if [ -z "$DEV" ]; then
    echo "Błąd: Musisz podać interfejs sieciowy (-i <interfejs>)."
    exit 1
fi

# =========================================================================
# AUTOMATYZACJA RDZENI: Wykrywanie wszystkich wątków logicznych procesora
# =========================================================================
CPUS_COUNT=$(nproc)
F_THREAD=0
L_THREAD=$((CPUS_COUNT - 1))

echo "=== Wykryto rdzenie logiczne: $CPUS_COUNT. Mapowanie wątków: 0 do $L_THREAD ==="

# Konfiguracja wydajnościowa (Maksymalny Stres-Test)
COUNT="0"             # 0 = nieskończony flood (zatrzymanie przez Ctrl+C)
CLONE_SKB="100000"    # Klonowanie pakietów w pamięci jądra
BURST="32"            # Pakowanie ramek do kolejki sieciowej
PKT_SIZE="60"         # Najmniejszy możliwy pakiet

# Auto-detekcja MAC jeśli nie podano
if [ -z "$DST_MAC" ]; then
    echo "🔍 Szukanie adresu MAC dla $DEST_IP..."
    ping -c 1 -W 1 $DEST_IP > /dev/null
    DST_MAC=$(ip neighbor show $DEST_IP | awk '{print $5}' | grep -E '([0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2}')
    if [ -z "$DST_MAC" ]; then
        echo "⚠️  Nie znaleziono MAC dla $DEST_IP. Używam domyślnego (może nie działać!)."
        DST_MAC="90:e2:ba:ff:ff:ff"
    else
        echo "✅ Znaleziono MAC: $DST_MAC"
    fi
fi

# Losowość portów źródłowych (Wymusza działanie RSS)
UDP_SRC_MIN=9
UDP_SRC_MAX=109

# Reset poprzedniej konfiguracji
pg_ctrl "reset"

# Pętla konfigurująca dedykowany wątek dla każdego rdzenia CPU
for ((thread = $F_THREAD; thread <= $L_THREAD; thread++)); do
    cur_dev=${DEV}@${thread}

    pg_thread $thread "rem_device_all"
    pg_thread $thread "add_device" $cur_dev

    # Mapowanie wątku pktgen bezpośrednio do numeru CPU
    pg_set $cur_dev "flag QUEUE_MAP_CPU"

    # Parametry generowania ruchu
    pg_set $cur_dev "count $COUNT"
    pg_set $cur_dev "clone_skb $CLONE_SKB"
    pg_set $cur_dev "pkt_size $PKT_SIZE"
    pg_set $cur_dev "delay 0" 
    pg_set $cur_dev "burst $BURST"

    # Wyłączenie timestampingu
    pg_set $cur_dev "flag NO_TIMESTAMP"

    # Adresowanie
    pg_set $cur_dev "dst_mac $DST_MAC"
    pg_set $cur_dev "dst $DEST_IP"

    # Losowanie portu źródłowego
    pg_set $cur_dev "flag UDPSRC_RND"
    pg_set $cur_dev "udp_src_min $UDP_SRC_MIN"
    pg_set $cur_dev "udp_src_max $UDP_SRC_MAX"
done

function print_result() {
    echo ""
    echo "========================================="
    echo "       WYNIKI GENEROWANIA RUCHU          "
    echo "========================================="
    total_pps=0
    for ((thread = $F_THREAD; thread <= $L_THREAD; thread++)); do
        cur_dev=${DEV}@${thread}
        pps=$(grep pps /proc/net/pktgen/$cur_dev | awk '{print $2}')
        echo "--> Wątek $thread ($cur_dev): $pps PPS"
        total_pps=$((total_pps + pps))
    done
    echo "========================================="
    echo " SUMARYCZNIE: $total_pps PPS"
    echo "========================================="
}

# Trap dla Ctrl+C
trap "echo 'Zatrzymywanie...'; pg_ctrl 'stop'; print_result; exit" SIGINT

echo "🚀 Uruchamianie floodu do: $DEST_IP (MAC: $DST_MAC) na interfejsie $DEV..."
echo "Wciśnij Ctrl+C, aby ZATRZYMAĆ i zobaczyć statystyki."

pg_ctrl "start"
while true; do sleep 1; done
