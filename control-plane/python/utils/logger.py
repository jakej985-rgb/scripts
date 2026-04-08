import logging
import os
from .paths import LOGS_DIR

def get_logger(name):
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    
    if not logger.handlers:
        log_file = os.path.join(LOGS_DIR, f"{name}.log")
        handler = logging.FileHandler(log_file)
        formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(name)s: %(message)s')
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        
        # Also log to console for development
        console = logging.StreamHandler()
        console.setFormatter(formatter)
        logger.addHandler(console)
        
    return logger
