#!/usr/bin/env python3
import time
import sys
import os
import argparse
from bcc import BPF

# Dołączenie ścieżki absolutnej w celu poprawnego importu z tego samego katalogu
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from utils import setup_logger, int_to_ip

def main():
    # 1. Konfiguracja argumentów uruchomieniowych (zgodnie z dokumentacją)
    parser = argparse.ArgumentParser(description="XDP-L2-Guard eBPF Control Plane")
    parser.add_argument("-i", "--interface", required=True, help="Interfejs sieciowy, np. eth0")
    parser.add_argument("--generic", action="store_true", help="Wymusza tryb wirtualny XDP (Generic/SKB Mode)")
    args = parser.parse_args()

    logger = setup_logger()
    interface = args.interface

    # Pobranie bezwzględnej ścieżki do pliku źródłowego C
    bpf_source_file = os.path.join(os.path.dirname(__file__), "../data_plane/filter.c")

    logger.info(f"Rozpoczynam inicjalizację silnika na interfejsie: {interface}")

    # 2. Inicjalizacja Just-In-Time z użyciem wbudowanego resolwera include w BCC
    try:
        b = BPF(src_file=bpf_source_file)
        logger.info("Kompilacja środowiska LLVM JIT zakończona sukcesem.")
    except Exception as e:
        logger.error(f"Błąd kompilacji maszyny eBPF Verifier: {e}")
        sys.exit(1)

    # 3. Flagi podpinania: 1<<1 to Generic (SKB), 1<<2 to Native (DRV)
    xdp_flags = 0
    if args.generic:
        xdp_flags |= (1 << 1)
        logger.info("Żądanie emulacji – używam trybu Generic (SKB).")
    else:
        xdp_flags |= (1 << 2)
        logger.info("Żądanie wysokiej wydajności – próba trybu Native XDP...")

    # 4. Aplikacja reguł XDP na warstwie sterownika
    try:
        fn = b.load_func("xdp_drop_logic", BPF.XDP)
        b.attach_xdp(dev=interface, fn=fn, flags=xdp_flags)
        logger.info("Pomyślnie związano NAPI Hook ze sterownikiem adaptera.")
    except Exception as e:
        logger.error(f"Krytyczny błąd montowania podsystemu: {e}")
        logger.info("Wskazówka: Wyłącz offloading sprzętowy komendą 'ethtool -K <interface> gro off'!")
        sys.exit(1)

    # Nawiązanie uchwytu do pamięci jądra współdzielonej z Data Plane
    blacklist_map = b.get_table("blacklist_ips")
    logger.info("Silnik uruchomiony. Monitorowanie asynchroniczne trwa (Ctrl+C przerywa).")

    # 5. Pętla pollingu map eBPF i eleganckie zakończenie pracy
    try:
        while True:
            time.sleep(1)
            if len(blacklist_map) > 0:
                print("\n" + "━"*50)
                logger.info("Aktywne blokady na warstwie eXpress Data Path:")
                for k, v in blacklist_map.items():
                    ip_addr = int_to_ip(k.value)
                    logger.info(f" ➔ Adres źródłowy [{ip_addr}] zablokowano: {v.value} ramek")
                print("━"*50)
            else:
                # Wskaźnik, że system żyje i jest gotowy
                sys.stdout.write("🛡️ ")
                sys.stdout.flush()
    except KeyboardInterrupt:
        print("\n")
        logger.info("Wychwycono SIGINT. Demontowanie logiki Data Plane...")
    finally:
        b.remove_xdp(dev=interface, flags=xdp_flags)
        logger.info(f"Odepnięto reguły z {interface}. Pamięć DMA zwolniona i bezpieczna.")

if __name__ == "__main__":
    main()