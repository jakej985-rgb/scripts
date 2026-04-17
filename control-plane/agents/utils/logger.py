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
        try:
            # Use RotatingFileHandler to prevent log sprawl
            fh = RotatingFileHandler(log_file, maxBytes=10*1024*1024, backupCount=3)
        except (PermissionError, OSError):
            # Fallback for Windows/Docker Desktop locking issues
            # If the primary log is locked, try a PID-specific log
            try:
                log_file = os.path.join(LOG_DIR, f"{name}_{os.getpid()}.log")
                fh = RotatingFileHandler(log_file, maxBytes=10*1024*1024, backupCount=3)
            except (PermissionError, OSError):
                # Final fallback: just skip file logging for this instance
                # The orchestrator is likely already capturing stdout
                return logger
            
        fh.setFormatter(formatter)
        logger.addHandler(fh)
    except Exception:
        # Avoid crashing the agent just because logging failed
        pass

    # Console Handler — Only when running standalone (not under orchestrator/run.py)
    # When run.py spawns agents as subprocesses, it captures stdout already.
    # Adding a stdout handler in that case causes every line to appear twice.
    is_orchestrated = os.getenv("M3TAL_ORCHESTRATED") == "1"
    if not is_orchestrated:
        ch = logging.StreamHandler(sys.stdout)
        ch.setFormatter(formatter)
        logger.addHandler(ch)
        
    return logger
