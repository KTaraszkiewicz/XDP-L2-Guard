import socket
import struct
import logging

def setup_logger():
    logger = logging.getLogger("XDP-L2-Guard")
    logger.setLevel(logging.INFO)
    
    if not logger.handlers:
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s', datefmt='%H:%M:%S'))
        logger.addHandler(console_handler)
        
    return logger

def int_to_ip(ip_int):
    try:
        return socket.inet_ntoa(struct.pack("<L", ip_int))
    except struct.error:
        return "Invalid IP"
