import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from .paths import LOG_DIR

def get_logger(name):
    # Standardize logger to avoid duplicate handlers if called multiple times
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger
        
    logger.setLevel(logging.INFO)
    
    # Standard Format: Timestamp [LEVEL] Agent: Message
    formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(name)s: %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
    
    # File Handler with Rotation (10MB max, 3 backups)
    try:
        os.makedirs(LOG_DIR, exist_ok=True)
        log_file = os.path.join(LOG_DIR, f"{name}.log")
        # Use RotatingFileHandler to prevent log sprawl (Batch 3 T2)
        fh = RotatingFileHandler(log_file, maxBytes=10*1024*1024, backupCount=3)
        fh.setFormatter(formatter)
        logger.addHandler(fh)
    except Exception as e:
        print(f"Failed to initialize file logger for {name}: {e}")

    # Console Handler (Stdout for run.sh capture)
    ch = logging.StreamHandler(sys.stdout)
    ch.setFormatter(formatter)
    logger.addHandler(ch)
        
    return logger
