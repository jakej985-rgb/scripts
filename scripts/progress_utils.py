#!/usr/bin/env python3
import sys
import time
import threading
from typing import Optional

# Batch 16 Hardening: Force UTF-8 for Windows console resilience
if sys.stdout.encoding.lower() != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except (AttributeError, Exception):
        pass

def safe_print(msg: str):
    """Prints with a fallback for encoding issues (Batch 16)."""
    try:
        print(msg)
    except UnicodeEncodeError:
        # Fallback for old Windows consoles
        safe_msg = msg.encode('ascii', 'replace').decode('ascii')
        print(safe_msg)

# Colors
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BLUE = "\033[94m"
CYAN = "\033[96m"
DIM = "\033[2m"
BOLD = "\033[1m"
END = "\033[0m"

class Spinner:
    def __init__(self, message: str = "Working"):
        self.message = message
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self.chars = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]

    def _spin(self):
        idx = 0
        while not self._stop_event.is_set():
            try:
                sys.stdout.write(f"\r  {CYAN}{self.chars[idx]}{END} {self.message}...")
                sys.stdout.flush()
                idx = (idx + 1) % len(self.chars)
                time.sleep(0.08)
            except Exception:
                break
        sys.stdout.write("\r" + " " * (len(self.message) + 20) + "\r")
        sys.stdout.flush()

    def set_message(self, message: str):
        """Update the spinner message while running."""
        self.message = message

    def start(self):
        if not sys.stdout.isatty():
            print(f"  [WAIT] {self.message}...")
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._spin, daemon=True)
        self._thread.start()

    def stop(self, success: bool = True, final_msg: Optional[str] = None):
        self._stop_event.set()
        if self._thread:
            self._thread.join()
        
        symbol = f"{GREEN}✔{END}" if success else f"{RED}✘{END}"
        msg = final_msg or self.message
        safe_print(f"  {symbol} {msg}")

class ProgressBar:
    def __init__(self, total: int, prefix: str = "", width: int = 30):
        self.total = max(total, 1)
        self.prefix = prefix
        self.width = width
        self.current = 0

    def update(self, current: int, suffix: str = ""):
        self.current = current
        if not sys.stdout.isatty(): 
            return
            
        percent = 100 * (current / float(self.total))
        filled = int(self.width * current // self.total)
        bar = "█" * filled + "░" * (self.width - filled)
        
        # Ensure we move to a fresh line for the progress bar so it persists under the header
        sys.stdout.write(f"\r  {self.prefix} {CYAN}[{bar}]{END} {percent:.0f}% {DIM}{suffix}{END}")
        sys.stdout.flush()
        if current >= self.total:
            sys.stdout.write("\n")

def _format_elapsed(seconds: int) -> str:
    if seconds < 60:
        return f"{seconds}s"
    m, s = divmod(seconds, 60)
    return f"{m}m {s}s"

class Heartbeat:
    """Inactivity counter that handles synchronized printing to avoid line collisions."""
    def __init__(self, interval: int = 1):
        self.interval = interval
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._last_activity = time.time()
        self._last_label = "Initializing"
        self._lock = threading.Lock()

    def ping(self, label: str = ""):
        with self._lock:
            self._last_activity = time.time()
            if label:
                self._last_label = label

    def log(self, message: str):
        """Thread-safe log that clears the heartbeat line before printing."""
        with self._lock:
            if sys.stdout.isatty():
                # Clear line and move to start
                sys.stdout.write("\r" + " " * 80 + "\r")
                sys.stdout.flush()
            safe_print(message)

    def _pulse(self):
        while not self._stop_event.is_set():
            with self._lock:
                elapsed = int(time.time() - self._last_activity)
                label = self._last_label
                
                if sys.stdout.isatty():
                    idle_str = _format_elapsed(elapsed)
                    # Use DIM and spaces to pad out the line to prevent ghost characters
                    sys.stdout.write(f"\r  {DIM}⏳ {label} — idle {idle_str}{END}       ")
                    sys.stdout.flush()
            
            time.sleep(self.interval)

    def start(self):
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._pulse, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop_event.set()
        if self._thread:
            self._thread.join()
        if sys.stdout.isatty():
            sys.stdout.write("\r" + " " * 80 + "\r")
            sys.stdout.flush()

def log_step(step: int, total: int, message: str, bar: Optional[ProgressBar] = None):
    prefix = f"{BLUE}{BOLD}[INIT] Step {step}/{total}:{END}"
    safe_print(f"\n{prefix} {message}")
    if bar:
        bar.update(step, "")
