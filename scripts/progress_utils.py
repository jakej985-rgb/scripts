#!/usr/bin/env python3
import sys
import time
import threading
import shutil
import json
from pathlib import Path
from typing import Optional, Any, List, Dict

# Batch 16 Hardening: Force UTF-8 for Windows console resilience
if sys.stdout.encoding.lower() != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except (AttributeError, Exception):
        pass

# --- Configuration & Theme Loading --------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent # Root
THEME_FILE = BASE_DIR / "control-plane" / "state" / "theme.json"

# Default Neon Hot Pink & Orange
p_rgb = [255, 105, 180]
s_rgb = [255, 165, 0]

try:
    if THEME_FILE.exists():
        with open(THEME_FILE, 'r') as f:
            t_data = json.load(f)
            p_rgb = t_data.get("primary", {}).get("rgb", p_rgb)
            s_rgb = t_data.get("secondary", {}).get("rgb", s_rgb)
except:
    pass

def _rgb_ansi(rgb: List[int]) -> str:
    return f"\033[38;2;{rgb[0]};{rgb[1]};{rgb[2]}m"

GREEN = "\033[92m"   
PINK = _rgb_ansi(p_rgb)
ORANGE = _rgb_ansi(s_rgb)
RED = "\033[91m"     
DIM = "\033[2m"      
BOLD = "\033[1m"     
END = "\033[0m"      

# Shorthand aliases
CYAN = PINK
BLUE = ORANGE
MAGENTA = PINK
YELLOW = ORANGE

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
        print(f"\n{PINK}{BOLD}{'=' * width}{END}")
        print(f"{PINK}{BOLD}  {title.upper()}{END}")
        if subtitle:
            print(f"{ORANGE}  {subtitle}{END}")
        print(f"{PINK}{BOLD}{'=' * width}{END}\n")

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
                sys.stdout.write(f"\r  {ORANGE}{self.chars[idx]}{END} {self.message}...")
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
        self._vertical_offset = 0 
        ProgressBar._active_instance = self

    def update(self, current: int, suffix: str = ""):
        self.current = current
        self.suffix = suffix
        if not sys.stdout.isatty(): return
            
        percent = 100 * (current / float(self.total))
        filled = int(self.width * current // self.total)
        bar = f"{PINK}█{END}" * filled + f"{DIM}░{END}" * (self.width - filled)
        
        main_line_content = f"  {ORANGE}{self.prefix}{END} {bar} {PINK}{BOLD}{percent:.0f}%{END} {DIM}{suffix}{END}"
        cols, _ = shutil.get_terminal_size()
        
        timer_str = ""
        if self._tethered_hb:
            elapsed = int(time.time() - self._tethered_hb._last_activity)
            timer_str = f" {DIM}[idle {_format_elapsed(elapsed)}]{END}"
            
        sys.stdout.write("\r" + " " * (cols - 1) + "\r")
        
        visible_main_len = len(f"  {self.prefix} [{'#'*self.width}] {percent:.0f}% {suffix}")
        padding = cols - visible_main_len - 14 
        
        if padding > 0:
            sys.stdout.write(f"  {ORANGE}{self.prefix}{END} {bar} {PINK}{BOLD}{percent:.0f}%{END} {DIM}{suffix}{END}{' ' * padding}{timer_str}")
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
        bar = f"{PINK}━{END}" * filled + f"{DIM}━{END}" * (self.width - filled)
        
        cols, _ = shutil.get_terminal_size()
        offset = 1
        if ProgressBar._active_instance:
            offset = ProgressBar._active_instance._vertical_offset + 1
            sys.stdout.write(f"\033[{offset}A") 
        
        sys.stdout.write("\r" + " " * (cols - 1) + "\r")
        sys.stdout.write(f"    {DIM}└─{END} {bar} {PINK}{BOLD}{current}/{self.total}{END} {ORANGE}{label}{END}")
        
        if ProgressBar._active_instance:
            sys.stdout.write(f"\033[{offset}B\r") 
        sys.stdout.flush()

class LiveList:
    """Manages a block of lines for individual container statuses."""
    def __init__(self, items: List[str]):
        self.items = items
        self.statuses: Dict[str, str] = {item: "queued" for item in items}
        self.count = len(items)
        if ProgressBar._active_instance:
            ProgressBar._active_instance._vertical_offset = self.count
            for _ in range(self.count):
                sys.stdout.write("\n")
            sys.stdout.write("\r")
            sys.stdout.flush()

    def update(self, item: str, status: str, note: str = ""):
        if item not in self.statuses or not sys.stdout.isatty(): return
        self.statuses[item] = status
        
        cols, _ = shutil.get_terminal_size()
        idx = self.items.index(item)
        offset = self.count - idx
        if ProgressBar._active_instance:
            sys.stdout.write(f"\033[{offset}A") 
            sys.stdout.write("\r" + " " * (cols - 1) + "\r")
            
            s_lower = status.lower()
            if any(x in s_lower for x in ["running", "healthy", "done", "removed"]):
                color = GREEN
            elif any(x in s_lower for x in ["starting", "pulling", "preparing", "terminating", "launching"]):
                color = ORANGE
            elif any(x in s_lower for x in ["restarting", "exited", "unhealthy", "failed"]):
                color = RED
            else:
                color = DIM

            note_str = f" {DIM}({note}){END}" if note else ""
            sys.stdout.write(f"      {DIM}•{END} {ORANGE}{item}{END}: [{color}{status}{END}]{note_str}")
            
            sys.stdout.write(f"\033[{offset}B\r")
            sys.stdout.flush()

    def reset(self):
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
            safe_print(f"  {DIM}[{ts}]{END} {PINK}{symbol}{END} {message}")

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
                    sys.stdout.write(f"  {DIM}⏳ {ORANGE}{self._last_label}{END} — {PINK}idle {idle_str}{END}")
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
    prefix = f"{PINK}{BOLD}[{step}/{total}]{END}"
    if bar: bar.update(step, message)
    else: safe_print(f"\n{prefix} {message}")
