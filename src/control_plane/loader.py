#!/usr/bin/env python3
import time
import sys
import os
import argparse
import subprocess
import json
import struct

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from utils import setup_logger, int_to_ip

def run_cmd(cmd):
    """Pomocnicza funkcja do wywoływania komend shellowych"""
    return subprocess.run(cmd, shell=True, text=True, capture_output=True)

def main():
    parser = argparse.ArgumentParser(description="XDP-L2-Guard CO-RE Control Plane")
    parser.add_argument("-i", "--interface", required=True, help="Interfejs sieciowy, np. eth0")
    parser.add_argument("--generic", action="store_true", help="Wymusza tryb wirtualny XDP (xdpgeneric)")
    args = parser.parse_args()

    logger = setup_logger()
    interface = args.interface

    # Ścieżki
    control_plane_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.abspath(os.path.join(control_plane_dir, "../../"))
    bpf_obj_file = os.path.join(project_root, "src/data_plane/filter.o")

    logger.info(f"Rozpoczynam inicjalizację CO-RE na interfejsie: {interface}")

    # 1. Kompilacja AOT przy pomocy Makefile
    logger.info("Wyzwalanie kompilacji Ahead-of-Time...")
    compile_res = run_cmd(f"cd {project_root} && make")
    if compile_res.returncode != 0:
        logger.error(f"Błąd kompilacji CO-RE:\n{compile_res.stderr}")
        sys.exit(1)
    
    if not os.path.exists(bpf_obj_file):
        logger.error("Błąd krytyczny: Nie odnaleziono skompilowanego pliku filter.o!")
        sys.exit(1)

    # 2. Wybór trybu (Native / Generic)
    xdp_mode = "xdpgeneric" if args.generic else "xdpdrv"
    if not args.generic:
        logger.info("Żądanie wysokiej wydajności – przypinanie w trybie Native (xdpdrv)...")

    # 3. Przypięcie obiektu ELF do karty sieciowej używając natywnego iproute2
    # Czyszczenie poprzednich reguł specyficznymi komendami, aby usunąć "zombie"
    run_cmd(f"ip link set dev {interface} xdpgeneric off")
    run_cmd(f"ip link set dev {interface} xdpdrv off")
    run_cmd(f"ip link set dev {interface} xdp off") 
    
    # DODANA FLAGA -force: Gwarantuje nadpisanie starych programów XDP w jądrze
    attach_cmd = f"ip -force link set dev {interface} {xdp_mode} obj {bpf_obj_file} sec xdp"
    attach_res = run_cmd(attach_cmd)
    
    if attach_res.returncode != 0:
        logger.error(f"Krytyczny błąd montowania podsystemu:\n{attach_res.stderr}")
        logger.info(f"Wskazówka: Upewnij się, że wyłączyłeś offload komendą: sudo ethtool -K {interface} gro off gso off")
        sys.exit(1)

    logger.info("Pomyślnie wpięto ELF CO-RE do warstwy eXpress Data Path.")
    logger.info("Silnik uruchomiony. Monitorowanie asynchroniczne trwa (Ctrl+C przerywa).")

    # 4. Pętla pollingu map eBPF za pomocą narzędzia bpftool
    try:
        while True:
            time.sleep(1)
            # Pobieramy zrzut mapy blacklist_ips w formacie JSON
            dump_res = run_cmd("bpftool -j map dump name blacklist_ips")
            
            if dump_res.returncode == 0 and dump_res.stdout.strip():
                map_data = json.loads(dump_res.stdout)
                
                if len(map_data) > 0:
                    print("\n" + "━"*50)
                    logger.info("Aktywne blokady na warstwie eXpress Data Path:")
                    
                    for item in map_data:
                        # bpftool zwraca tablice heksów np. ["0xc0", "0xa8", "0x01", "0x64"]
                        key_bytes = [int(x, 16) for x in item["key"]]
                        val_bytes = [int(x, 16) for x in item["value"]]
                        
                        # Dekodujemy little-endian do natywnych typów
                        ip_int = struct.unpack("<I", bytes(key_bytes))[0]
                        drop_count = struct.unpack("<Q", bytes(val_bytes))[0]
                        
                        ip_addr = int_to_ip(ip_int)
                        logger.info(f" ➔ Adres źródłowy [{ip_addr}] zablokowano: {drop_count} ramek")
                    print("━"*50)
                else:
                    sys.stdout.write("🛡️ ")
                    sys.stdout.flush()
            else:
                sys.stdout.write("🛡️ ")
                sys.stdout.flush()

    except KeyboardInterrupt:
        print("\n")
        logger.info("Wychwycono SIGINT. Demontowanie logiki Data Plane...")
    finally:
        # 5. Bezpieczne odpięcie środowiska CO-RE - celujemy prosto w używany tryb
        run_cmd(f"ip link set dev {interface} {xdp_mode} off")
        run_cmd(f"ip link set dev {interface} xdp off")
        logger.info(f"Odepnięto reguły z {interface}. Pamięć DMA zwolniona i bezpieczna.")

if __name__ == "__main__":
    main()