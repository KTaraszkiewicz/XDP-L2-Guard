import socket
import struct
import logging

def setup_logger():
    """
    Konfiguracja profesjonalnego loggera dla środowiska Control Plane.
    Gwarantuje czytelne logi z timestampami podczas działania loadera.
    """
    logger = logging.getLogger("XDP-L2-Guard")
    logger.setLevel(logging.INFO)
    
    # Zapobieganie podwójnemu logowaniu
    if not logger.handlers:
        console_handler = logging.StreamHandler()
        formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s', datefmt='%H:%M:%S')
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
        
    return logger

def int_to_ip(ip_int):
    """
    Konwersja adresu IP wyciągniętego z mapy eBPF (z formatu little-endian uint32)
    na format czytelnego stringa IPv4 (np. 192.168.1.100).
    """
    try:
        return socket.inet_ntoa(struct.pack("<L", ip_int))
    except struct.error:
        return "Invalid IP"