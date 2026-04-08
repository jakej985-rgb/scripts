import logging
import os
import sys
from .paths import LOG_DIR

def get_logger(name):
    # Standardize logger to avoid duplicate handlers if called multiple times
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger
        
    logger.setLevel(logging.INFO)
    
    # Standard Format: Timestamp [LEVEL] Agent: Message
    formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(name)s: %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
    
    # File Handler
    try:
        os.makedirs(LOG_DIR, exist_ok=True)
        log_file = os.path.join(LOG_DIR, f"{name}.log")
        fh = logging.FileHandler(log_file)
        fh.setFormatter(formatter)
        logger.addHandler(fh)
    except Exception as e:
        print(f"Failed to initialize file logger for {name}: {e}")

    # Console Handler (Stdout for run.sh capture)
    ch = logging.StreamHandler(sys.stdout)
    ch.setFormatter(formatter)
    logger.addHandler(ch)
        
    return logger
