#!/usr/bin/env python3
import sys
import time
import threading
import shutil
from typing import Optional, Any, List, Dict

# Batch 16 Hardening: Force UTF-8 for Windows console resilience
if sys.stdout.encoding.lower() != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except (AttributeError, Exception):
        pass

# Colors
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BLUE = "\033[94m"
CYAN = "\033[96m"
MAGENTA = "\033[95m"
DIM = "\033[2m"
BOLD = "\033[1m"
END = "\033[0m"

def safe_print(msg: str):
    """Prints with a fallback for encoding issues."""
    try:
        sys.stdout.write(msg + "\n")
        sys.stdout.flush()
    except UnicodeEncodeError:
        safe_msg = msg.encode('ascii', 'replace').decode('ascii')
        sys.stdout.write(safe_msg + "\n")
        sys.stdout.flush()

class Header:
    @staticmethod
    def show(title: str, subtitle: str = ""):
        width = 60
        print(f"\n{CYAN}{BOLD}{'=' * width}{END}")
        print(f"{CYAN}{BOLD}  {title.upper()}{END}")
        if subtitle:
            print(f"{DIM}  {subtitle}{END}")
        print(f"{CYAN}{BOLD}{'=' * width}{END}\n")

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

    def start(self):
        if not sys.stdout.isatty(): return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._spin, daemon=True)
        self._thread.start()

    def stop(self, success: bool = True, final_msg: Optional[str] = None):
        self._stop_event.set()
        if self._thread: self._thread.join()
        symbol = f"{GREEN}✔{END}" if success else f"{RED}✘{END}"
        msg = final_msg or self.message
        safe_print(f"  {symbol} {msg}")

class ProgressBar:
    _active_instance = None 

    def __init__(self, total: int, prefix: str = "", width: int = 30):
        self.total = max(total, 1)
        self.prefix = prefix
        self.width = width
        self.current = 0
        self.suffix = ""
        self._tethered_hb: Optional[Any] = None
        self._vertical_offset = 0 # How many sub-lines are above us
        ProgressBar._active_instance = self

    def update(self, current: int, suffix: str = ""):
        self.current = current
        self.suffix = suffix
        if not sys.stdout.isatty(): return
            
        percent = 100 * (current / float(self.total))
        filled = int(self.width * current // self.total)
        bar = f"{CYAN}█{END}" * filled + f"{DIM}░{END}" * (self.width - filled)
        
        main_line_content = f"  {self.prefix} {bar} {BOLD}{percent:.0f}%{END} {DIM}{suffix}{END}"
        cols, _ = shutil.get_terminal_size()
        
        # Integrated Timer
        timer_str = ""
        if self._tethered_hb:
            elapsed = int(time.time() - self._tethered_hb._last_activity)
            timer_str = f" {DIM}[idle {_format_elapsed(elapsed)}]{END}"
            
        # Clear line completely then print to avoid ghost text
        sys.stdout.write("\r" + " " * (cols - 1) + "\r")
        
        # Push timer to right if there is space
        visible_main_len = len(f"  {self.prefix} [{'#'*self.width}] {percent:.0f}% {suffix}")
        padding = cols - visible_main_len - 14 # 14 is approx len of [idle XXs]
        
        if padding > 0:
            sys.stdout.write(f"  {self.prefix} {bar} {BOLD}{percent:.0f}%{END} {DIM}{suffix}{END}{' ' * padding}{timer_str}")
        else:
            sys.stdout.write(f"{main_line_content}{timer_str}")
            
        sys.stdout.flush()
        if current >= self.total:
            sys.stdout.write("\n")

class SubProgressBar:
    """A compact, one-line progress bar for sub-tasks."""
    def __init__(self, total: int, width: int = 20):
        self.total = max(total, 1)
        self.width = width

    def update(self, current: int, label: str = ""):
        if not sys.stdout.isatty(): return
        filled = int(self.width * current // self.total)
        bar = f"{MAGENTA}━{END}" * filled + f"{DIM}━{END}" * (self.width - filled)
        
        cols, _ = shutil.get_terminal_size()
        offset = 1
        if ProgressBar._active_instance:
            offset = ProgressBar._active_instance._vertical_offset + 1
            sys.stdout.write(f"\033[{offset}A") # Move up
        
        # Clear line then print
        sys.stdout.write("\r" + " " * (cols - 1) + "\r")
        sys.stdout.write(f"    {DIM}└─{END} {bar} {BOLD}{current}/{self.total}{END} {DIM}{label}{END}")
        
        if ProgressBar._active_instance:
            sys.stdout.write(f"\033[{offset}B\r") # Move back down
        sys.stdout.flush()

class LiveList:
    """Manages a block of lines for individual container statuses."""
    def __init__(self, items: List[str]):
        self.items = items
        self.statuses: Dict[str, str] = {item: "queued" for item in items}
        self.count = len(items)
        # Register offset with the main bar
        if ProgressBar._active_instance:
            ProgressBar._active_instance._vertical_offset = self.count
            # Print initial empty lines to occupy space
            for _ in range(self.count):
                sys.stdout.write("\n")
            sys.stdout.write("\r") # Reset to start of line below
            sys.stdout.flush()

    def update(self, item: str, status: str, note: str = ""):
        if item not in self.statuses or not sys.stdout.isatty(): return
        self.statuses[item] = status
        
        cols, _ = shutil.get_terminal_size()
        idx = self.items.index(item)
        offset = self.count - idx
        if ProgressBar._active_instance:
            sys.stdout.write(f"\033[{offset}A") # Go up to item line
            sys.stdout.write("\r" + " " * (cols - 1) + "\r")
            
            # Color mapping
            s_lower = status.lower()
            if any(x in s_lower for x in ["running", "healthy", "done", "removed"]):
                color = GREEN
            elif any(x in s_lower for x in ["starting", "pulling", "preparing", "terminating"]):
                color = YELLOW
            elif any(x in s_lower for x in ["restarting", "exited", "unhealthy", "failed"]):
                color = RED
            else:
                color = DIM

            note_str = f" {DIM}({note}){END}" if note else ""
            sys.stdout.write(f"      {DIM}•{END} {item}: [{color}{status}{END}]{note_str}")
            
            sys.stdout.write(f"\033[{offset}B\r") # Go back down
            sys.stdout.flush()

    def reset(self):
        """Called when stack orchestration is complete to 'lock' the lines."""
        if ProgressBar._active_instance:
            ProgressBar._active_instance._vertical_offset = 0

def _format_elapsed(seconds: int) -> str:
    if seconds < 60: return f"{seconds}s"
    m, s = divmod(seconds, 60)
    return f"{m}m {s}s"

class Heartbeat:
    def __init__(self, interval: int = 1):
        self.interval = interval
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._last_activity = time.time()
        self._last_label = "Initializing"
        self._lock = threading.Lock()
        self._tethered_bar: Optional[ProgressBar] = None

    def tether(self, bar: ProgressBar):
        self._tethered_bar = bar
        bar._tethered_hb = self

    def ping(self, label: str = ""):
        with self._lock:
            self._last_activity = time.time()
            if label: self._last_label = label

    def log(self, message: str, symbol: str = "•"):
        with self._lock:
            ts = time.strftime("%H:%M:%S")
            if sys.stdout.isatty():
                cols, _ = shutil.get_terminal_size()
                sys.stdout.write("\r" + " " * (cols - 1) + "\r")
            safe_print(f"  {DIM}[{ts}]{END} {CYAN}{symbol}{END} {message}")

    def _pulse(self):
        while not self._stop_event.is_set():
            with self._lock:
                if self._tethered_bar:
                    self._tethered_bar.update(self._tethered_bar.current, self._tethered_bar.suffix)
                elif sys.stdout.isatty():
                    cols, _ = shutil.get_terminal_size()
                    elapsed = int(time.time() - self._last_activity)
                    idle_str = _format_elapsed(elapsed)
                    sys.stdout.write("\r" + " " * (cols - 1) + "\r")
                    sys.stdout.write(f"  {DIM}⏳ {self._last_label} — idle {idle_str}{END}")
                    sys.stdout.flush()
            time.sleep(self.interval)

    def start(self):
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._pulse, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop_event.set()
        if self._thread: self._thread.join()
        if sys.stdout.isatty():
            cols, _ = shutil.get_terminal_size()
            sys.stdout.write("\r" + " " * (cols - 1) + "\r")
            sys.stdout.flush()

def log_step(step: int, total: int, message: str, bar: Optional[ProgressBar] = None):
    prefix = f"{BLUE}{BOLD}[{step}/{total}]{END}"
    if bar: bar.update(step, message)
    else: safe_print(f"\n{prefix} {message}")
