#!/bin/bash
# SPDX-License-Identifier: GPL-2.0
#
# Zoptymalizowany pod maksymalny PPS dla testów porównawczych XDP vs nftables/iptables
# Automatycznie wykorzystuje wszystkie dostępne rdzenie logiczne procesora.

basedir=`dirname $0`
source ${basedir}/functions.sh
root_check_run_with_sudo "$@"

# 1. Logika pobierania IP jako pierwszego argumentu
if [ -z "$1" ] || [[ "$1" == -* ]]; then
    echo "Błąd: Brak docelowego adresu IP."
    echo "Użycie: $0 <Adres_IP_Celu> -i <Interfejs_sieciowy>"
    echo "Przykład: $0 192.168.1.50 -i enp3s0"
    exit 1
fi

DEST_IP=$1
shift # Przesuwamy argumenty, aby parameters.sh mógł obsłużyć resztę (np. -i dla interfejsu)

source ${basedir}/parameters.sh

# Trap EXIT first
trap_exit

# =========================================================================
# AUTOMATYZACJA RDZENI: Wykrywanie wszystkich wątków logicznych procesora
# =========================================================================
CPUS_COUNT=$(nproc)
F_THREAD=0
L_THREAD=$((CPUS_COUNT - 1))

echo "=== Wykryto rdzenie logiczne: $CPUS_COUNT. Mapowanie wątków: 0 do $L_THREAD ==="

# Konfiguracja wydajnościowa (Maksymalny Stres-Test)
COUNT="0"             # 0 = nieskończony flood (zatrzymanie przez Ctrl+C)
CLONE_SKB="100000"    # Klonowanie pakietów w pamięci jądra (omija alokację i drastycznie podnosi PPS)
BURST="32"            # Pakowanie ramek do kolejki sieciowej (xmit_more)
PKT_SIZE="60"         # Najmniejszy możliwy pakiet (60B + 4B CRC = 64B na kablu) - klucz do testowania XDP

# !!! WAŻNE: Wpisz tutaj adres MAC karty sieciowej komputera docelowego (Celu) !!!
[ -z "$DST_MAC" ] && DST_MAC="90:e2:ba:ff:ff:ff"

# Losowość portów źródłowych (Wymusza działanie RSS / multiqueue na karcie celu)
UDP_SRC_MIN=9
UDP_SRC_MAX=109

if [ -n "$DEST_IP" ]; then
    validate_addr${IP6} $DEST_IP
    read -r DST_MIN DST_MAX <<< $(parse_addr${IP6} $DEST_IP)
fi
if [ -n "$DST_PORT" ]; then
    read -r UDP_DST_MIN UDP_DST_MAX <<< $(parse_ports $DST_PORT)
    validate_ports $UDP_DST_MIN $UDP_DST_MAX
fi

# Reset poprzedniej konfiguracji
[ -z "$APPEND" ] && pg_ctrl "reset"

# Pętla konfigurująca dedykowany wątek dla każdego rdzenia CPU
for ((thread = $F_THREAD; thread <= $L_THREAD; thread++)); do
    dev=${DEV}@${thread}

    [ -z "$APPEND" ] && pg_thread $thread "rem_device_all"
    pg_thread $thread "add_device" $dev

    # Mapowanie wątku pktgen bezpośrednio do numeru CPU (1:1)
    pg_set $dev "flag QUEUE_MAP_CPU"

    # Parametry generowania ruchu
    pg_set $dev "count $COUNT"
    pg_set $dev "clone_skb $CLONE_SKB"
    pg_set $dev "pkt_size $PKT_SIZE"
    pg_set $dev "delay 0" 
    pg_set $dev "burst $BURST"

    # Wyłączenie timestampingu dla zaoszczędzenia cykli CPU
    pg_set $dev "flag NO_TIMESTAMP"

    # Adresowanie
    pg_set $dev "dst_mac $DST_MAC"
    pg_set $dev "dst${IP6}_min $DST_MIN"
    pg_set $dev "dst${IP6}_max $DST_MAX"

    if [ -n "$DST_PORT" ]; then
        pg_set $dev "flag UDPDST_RND"
        pg_set $dev "udp_dst_min $UDP_DST_MIN"
        pg_set $dev "udp_dst_max $UDP_DST_MAX"
    fi

    [ ! -z "$UDP_CSUM" ] && pg_set $dev "flag UDPCSUM"

    # Losowanie portu źródłowego - kluczowe dla rozbicia ruchu na wiele kolejek RX na celu
    pg_set $dev "flag UDPSRC_RND"
    pg_set $dev "udp_src_min $UDP_SRC_MIN"
    pg_set $dev "udp_src_max $UDP_SRC_MAX"
done

function print_result() {
    echo ""
    echo "========================================="
    echo "       WYNIKI GENEROWANIA RUCHU          "
    echo "========================================="
    for ((thread = $F_THREAD; thread <= $L_THREAD; thread++)); do
        dev=${DEV}@${thread}
        echo "--> Wątek (Rdzeń) $thread ($dev):"
        cat /proc/net/pktgen/$dev | grep -A2 "Result:"
        echo "-----------------------------------------"
    done
}

trap true SIGINT

if [ -z "$APPEND" ]; then
    echo "Uruchamianie floodu do: $DEST_IP (MAC: $DST_MAC)..." >&2
    echo "Wciśnij Ctrl+C, aby ZATRZYMAĆ i zobaczyć statystyki PPS." >&2
    pg_ctrl "start"
    echo "Zakończono." >&2

    print_result
else
    echo "Tryb Append: Konfiguracja zakończona."
fi