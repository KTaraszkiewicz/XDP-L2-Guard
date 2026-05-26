import socket
import struct
import logging

def setup_logger():
    """
    Configures a professional logger for the Control Plane environment.
    Ensures readable logs with timestamps during loader execution.
    """
    logger = logging.getLogger("XDP-L2-Guard")
    logger.setLevel(logging.INFO)
    
    # Prevent duplicate logging
    if not logger.handlers:
        console_handler = logging.StreamHandler()
        formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s', datefmt='%H:%M:%S')
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
        
    return logger

def int_to_ip(ip_int):
    """
    Converts an IP address extracted from an eBPF map (in little-endian uint32 format)
    to a human-readable IPv4 string (e.g., 192.168.1.100).
    """
    try:
        # Convert little-endian integer to standard IPv4 dotted-quad string
        return socket.inet_ntoa(struct.pack("<L", ip_int))
    except struct.error:
        return "Invalid IP"