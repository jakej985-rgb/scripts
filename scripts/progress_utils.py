#!/usr/bin/env python3
import sys
import time
import threading
from typing import Optional

# Colors
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BLUE = "\033[94m"
BOLD = "\033[1m"
END = "\033[0m"

class Spinner:
    def __init__(self, message: str = "Working"):
        self.message = message
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self.chars = ["|", "/", "-", "\\"]

    def _spin(self):
        idx = 0
        while not self._stop_event.is_set():
            try:
                # Clear line and print
                sys.stdout.write(f"\r  {BLUE}{self.chars[idx]}{END} {self.message}...")
                sys.stdout.flush()
                idx = (idx + 1) % len(self.chars)
                time.sleep(0.12)
            except Exception:
                # If stdout fails (e.g. broken pipe or encoding), stop spinning silently
                break
        # Final cleanup line
        sys.stdout.write("\r" + " " * (len(self.message) + 20) + "\r")
        sys.stdout.flush()

    def set_message(self, message: str):
        """Update the spinner message while running."""
        self.message = message

    def start(self):
        if not sys.stdout.isatty():
            print(f"  [INIT] {self.message}...")
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._spin, daemon=True)
        self._thread.start()

    def stop(self, success: bool = True, final_msg: Optional[str] = None):
        self._stop_event.set()
        if self._thread:
            self._thread.join()
        
        if sys.stdout.isatty():
            symbol = f"{GREEN}V{END}" if success else f"{RED}X{END}"
            msg = final_msg or self.message
            print(f"  {symbol} {msg}")

class ProgressBar:
    def __init__(self, total: int, prefix: str = "", width: int = 30):
        self.total = total
        self.prefix = prefix
        self.width = width
        self.current = 0

    def update(self, current: int, suffix: str = ""):
        self.current = current
        if not sys.stdout.isatty(): 
            return
            
        percent = 100 * (current / float(self.total))
        filled = int(self.width * current // self.total)
        bar = "█" * filled + "-" * (self.width - filled)
        
        sys.stdout.write(f"\r  {self.prefix} [{bar}] {percent:.1f}% {suffix}")
        sys.stdout.flush()
        if current >= self.total:
            sys.stdout.write("\n")

class Heartbeat:
    def __init__(self, interval: int = 15):
        self.interval = interval
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def _pulse(self):
        last_pulse = time.time()
        while not self._stop_event.is_set():
            if time.time() - last_pulse >= self.interval:
                ts = time.strftime("%H:%M:%S")
                sys.stdout.write(f"\n{YELLOW}[HEARTBEAT] {ts}: System is still working...{END}\n")
                sys.stdout.flush()
                last_pulse = time.time()
            time.sleep(1)

    def start(self):
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._pulse, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop_event.set()
        if self._thread:
            self._thread.join()

def log_step(step: int, total: int, message: str):
    prefix = f"{BLUE}{BOLD}[INIT] Step {step}/{total}:{END}"
    print(f"\n{prefix} {message}")
