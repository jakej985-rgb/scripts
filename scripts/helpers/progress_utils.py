#!/usr/bin/env python3
import os
import sys
import time
import threading
import shutil
import json
import re
import ctypes
try:
    if os.name == 'nt':
        # Force Virtual Terminal Processing for Windows 10+
        kernel32 = ctypes.windll.kernel32
        # SetConsoleMode(STD_OUTPUT_HANDLE, ENABLE_VIRTUAL_TERMINAL_PROCESSING | ENABLE_PROCESSED_OUTPUT)
        kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
except Exception:
    pass

try:
    import colorama
    colorama.init(autoreset=True)
except ImportError:
    if os.name == 'nt':
        os.system('') # Fallback for Windows ANSI
from pathlib import Path
from typing import Optional, List, Dict

# Batch 16 Hardening: Force UTF-8 for Windows console resilience
if sys.stdout.encoding.lower() != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except (AttributeError, Exception):
        pass

# UI Synchronization Lock
UI_LOCK = threading.RLock()
UI_ACTIVE = True
IS_TTY = sys.stdout.isatty()
ACTIVE_UIS = []
GLOBAL_LAST_LINES = 0  # CRITICAL: Tracks what's actually on the terminal
GLOBAL_COUNTER = 0      # For deterministic creation order
SESSION_START = time.time()  # Global session timer for right-aligned total
_LAST_FRAME = ""  # Dedup cache to prevent identical redraws

# --- Configuration & Theme Loading --------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent.parent # Repo Root
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
except Exception:
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

# Pre-compiled ANSI stripper for width calculations
_ANSI_RE = re.compile(r'\033\[[0-9;]*m')

# --- Global UI Management Engine ---

def _clear_ui_unlocked():
    """Surgical line-by-line clearing. Deterministic and log-safe."""
    if not IS_TTY: return
    global GLOBAL_LAST_LINES
    if GLOBAL_LAST_LINES > 0:
        # User Fix Tip: Controlled line clearing loop
        # Clear CURRENT line -> Move UP -> Repeat
        for _ in range(GLOBAL_LAST_LINES):
            sys.stdout.write("\033[2K") # Clear line
            sys.stdout.write("\033[1A") # Move UP
        
        # Clear the top-most line we reached (ghost line prevention)
        sys.stdout.write("\033[2K")
        sys.stdout.flush()
        GLOBAL_LAST_LINES = 0

def _refresh_ui_unlocked():
    """Grand Architect: Batch collect and redraw."""
    if not IS_TTY: return
    global GLOBAL_LAST_LINES, _LAST_FRAME
    
    # Snapshot and sort for deterministic rendering
    with UI_LOCK:
        uis = sorted(ACTIVE_UIS, key=lambda u: (u.render_priority, u.creation_index))
    
    all_lines = []
    for ui in uis:
        all_lines.extend(ui._render_lines())
    
    if not all_lines:
        _clear_ui_unlocked()
        GLOBAL_LAST_LINES = 0
        _LAST_FRAME = ""
        return

    # Dedup: Skip identical redraws to prevent flicker
    frame_str = "\n".join(all_lines)
    if frame_str == _LAST_FRAME and GLOBAL_LAST_LINES == len(all_lines):
        return
    
    _clear_ui_unlocked()

    # Write entire frame with per-line clearing
    output = []
    for line in all_lines:
        output.append(f"\033[2K{line}") # Clear line before writing
    
    sys.stdout.write("\n".join(output) + "\n")
    sys.stdout.flush() # User Fix Tip: Always flush batch writes
    
    GLOBAL_LAST_LINES = len(all_lines)
    _LAST_FRAME = frame_str

def request_render():
    """Unified entry point for UI updates."""
    with UI_LOCK:
        if UI_ACTIVE:
            _refresh_ui_unlocked()

def refresh_ui():
    """Public thread-safe trigger for a UI redraw."""
    with UI_LOCK:
        if UI_ACTIVE:
            _refresh_ui_unlocked()

def reset_session_timer():
    """Reset the global session timer (call at orchestration start)."""
    global SESSION_START
    SESSION_START = time.time()

def safe_print(*args, **kwargs):
    """Thread-safe, layout-aware print with TTY and Encoding fallback."""
    with UI_LOCK:
        global UI_ACTIVE, _LAST_FRAME
        
        # Snapshot state
        was_active = UI_ACTIVE
        UI_ACTIVE = False
        
        _clear_ui_unlocked()
        _LAST_FRAME = ""  # Invalidate dedup cache after log output
        
        msg = " ".join(str(a) for a in args)
        try:
            # Ensure final newline for canvas stability
            sys.stdout.write(msg + "\n")
        except UnicodeEncodeError:
            sys.stdout.write(msg.encode("utf-8", "replace").decode("utf-8") + "\n")
            
        sys.stdout.flush()
        
        UI_ACTIVE = was_active
        if UI_ACTIVE:
            _refresh_ui_unlocked()


class BaseUI:
    def __init__(self, priority: int = 10):
        global GLOBAL_COUNTER
        self.render_priority = priority
        self.creation_index = GLOBAL_COUNTER
        GLOBAL_COUNTER += 1
        
        self._last_rendered_lines = 0
        self._registered = False
        self._register()

    def _register(self):
        if not IS_TTY: return
        with UI_LOCK:
            if self not in ACTIVE_UIS:
                if UI_ACTIVE: _clear_ui_unlocked()
                ACTIVE_UIS.append(self)
                self._registered = True
                if UI_ACTIVE: _refresh_ui_unlocked()

    def _unregister(self):
        if not IS_TTY: return
        with UI_LOCK:
            if self in ACTIVE_UIS:
                if UI_ACTIVE: _clear_ui_unlocked()
                ACTIVE_UIS.remove(self)
                self._registered = False
                if UI_ACTIVE: _refresh_ui_unlocked()

    def __enter__(self):
        return self

    def __exit__(self, _exc_type, _exc_val, _exc_tb):
        self._unregister()

    def _render_lines(self) -> List[str]:
        return []


class Header:
    @staticmethod
    def show(title: str, subtitle: str = ""):
        width = 60
        lines = [
            f"\n{PINK}{BOLD}{'=' * width}{END}",
            f"{PINK}{BOLD}  {title.upper()}{END}"
        ]
        if subtitle:
            lines.append(f"{ORANGE}  {subtitle}{END}")
        lines.append(f"{PINK}{BOLD}{'=' * width}{END}\n")
        safe_print("\n".join(lines).strip("\n"))


class Spinner(BaseUI):
    def __init__(self, message: str = "Working"):
        # Set line requirements BEFORE init registers
        self._last_rendered_lines = 1
        self.message = message
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self.chars = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
        self.current_idx = 0
        super().__init__()

    def _render_lines(self) -> List[str]:
        return [f"  {ORANGE}{self.chars[self.current_idx]}{END} {self.message}..."]

    def _spin(self):
        if not IS_TTY: return
        while not self._stop_event.is_set():
            self.current_idx = (self.current_idx + 1) % len(self.chars)
            request_render()
            time.sleep(0.08)

    def start(self):
        if not IS_TTY: return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._spin, daemon=True)
        self._thread.start()

    def stop(self, success: bool = True, final_msg: Optional[str] = None):
        self._stop_event.set()
        if self._thread: self._thread.join()
        self._unregister()
        symbol = f"{GREEN}✔{END}" if success else f"{RED}✘{END}"
        msg = final_msg or self.message
        safe_print(f"  {symbol} {msg}")

def _format_elapsed(seconds: int) -> str:
    if seconds < 60: return f"{seconds}s"
    m, s = divmod(seconds, 60)
    return f"{m}m {s}s"

def _format_timer(seconds: float) -> str:
    m, s = divmod(int(seconds), 60)
    return f"{m:02}:{s:02}"

class Heartbeat:
    def __init__(self, interval: int = 1):
        self.interval = interval
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._last_activity = time.time()
        self._last_label = "Initializing"
        self._lock = threading.Lock()
        self._tethered_bar = None

    def tether(self, bar):
        self._tethered_bar = bar
        bar._tethered_hb = self

    def ping(self, label: str = ""):
        with self._lock:
            self._last_activity = time.time()
            if label: self._last_label = label

    def log(self, message: str, symbol: str = "•"):
        ts = time.strftime("%H:%M:%S")
        log_str = f"  {DIM}[{ts}]{END} {PINK}{symbol}{END} {message}"
        safe_print(log_str)

    def _pulse(self):
        while not self._stop_event.is_set():
            with self._lock:
                if self._tethered_bar:
                    # Pulsing the bar triggers its own request_render
                    self._tethered_bar.update(self._tethered_bar.current, self._tethered_bar.suffix)
                elif IS_TTY:
                    request_render()
            time.sleep(self.interval)

    def start(self):
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._pulse, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop_event.set()
        if self._thread: self._thread.join()
        if list(filter(lambda x: isinstance(x, Spinner), ACTIVE_UIS)):
             with UI_LOCK:
                 if UI_ACTIVE: _refresh_ui_unlocked()


class ProgressBar(BaseUI):
    _active_instance = None 

    def __init__(self, total: int, prefix: str = "", width: int = 30):
        self._last_rendered_lines = 1
        self.total = max(total, 1)
        self.prefix = prefix
        self.width = width
        self.current = 0
        self.suffix = ""
        self._tethered_hb = None
        ProgressBar._active_instance = self
        super().__init__()

    def _render_lines(self) -> List[str]:
        term_width = shutil.get_terminal_size().columns
        percent = 100 * (self.current / float(self.total))
        
        # Dynamic bar width: use ~1/3 of terminal, min 15, max 40
        bar_width = max(15, min(40, term_width // 3))
        filled = int(bar_width * self.current // self.total)
        bar = f"{PINK}█{END}" * filled + f"{DIM}░{END}" * (bar_width - filled)
        
        # Left side: label + bar + percent + suffix
        left = f"  {ORANGE}{self.prefix}{END} {bar} {PINK}{BOLD}{percent:.0f}%{END} {DIM}{self.suffix}{END}"
        
        # Right side: idle timer + total session timer
        idle_sec = 0
        if self._tethered_hb:
            idle_sec = time.time() - self._tethered_hb._last_activity
        total_sec = time.time() - SESSION_START
        right = f"{DIM}[idle {_format_timer(idle_sec)} | total {_format_timer(total_sec)}]{END}"
        
        # Calculate raw text lengths (strip ANSI for spacing math)
        left_len = len(_ANSI_RE.sub('', left))
        right_len = len(_ANSI_RE.sub('', right))
        spacing = max(1, term_width - left_len - right_len)
        
        return [left + (" " * spacing) + right]

    def update(self, current: int, suffix: str = "", redraw: bool = True):
        # User Tip: Components MUST NOT redraw in tight loops unnecessarily
        changed = (current != self.current or suffix != self.suffix)
        self.current = current
        self.suffix = suffix
        if changed and redraw:
            request_render()


class SubProgressBar(BaseUI):
    """A compact, one-line progress bar for sub-tasks."""
    def __init__(self, total: int, width: int = 20):
        self.total = max(total, 1)
        self.width = width
        self.current_val = 0
        self.current_label = ""
        # Sub Bars have higher priority (render below main bar)
        super().__init__(priority=20)

    def update(self, current: int, label: str = "", redraw: bool = True):
        changed = (current != self.current_val or label != self.current_label)
        self.current_val = current
        self.current_label = label
        if changed and redraw:
            request_render()

    def _render_lines(self) -> List[str]:
        term_width = shutil.get_terminal_size().columns
        # Sub bar: smaller, ~1/4 terminal width
        bar_width = max(10, min(25, term_width // 4))
        filled = int(bar_width * self.current_val // self.total)
        bar = f"{PINK}━{END}" * filled + f"{DIM}━{END}" * (bar_width - filled)
        return [f"    {DIM}└─{END} {bar} {PINK}{BOLD}{self.current_val}/{self.total}{END} {ORANGE}{self.current_label}{END}"]


class LiveList(BaseUI):
    """Manages a block of lines for individual container statuses."""
    def __init__(self, items: List[str]):
        self.items = items
        self.statuses: Dict[str, str] = {item: "queued" for item in items}
        self.times: Dict[str, float] = {item: time.time() for item in items}
        self.elapsed: Dict[str, Optional[float]] = {item: None for item in items}
        self.count = len(items)
        # Lists have highest priority (bottom of stack)
        super().__init__(priority=30)

    def add_items(self, new_items: List[str]):
        """Dynamically expand the live list with new services."""
        dirty = False
        for item in new_items:
            if item not in self.items:
                self.items.append(item)
                self.statuses[item] = "queued"
                self.times[item] = time.time()
                self.elapsed[item] = None
                dirty = True
        
        if dirty:
            self.count = len(self.items)
            request_render()

    def update(self, item: str, status: str, _note: str = "", redraw: bool = True):
        if item not in self.statuses: return
        
        changed = (self.statuses[item] != status)
        
        # Stop clock on terminal state
        s_lower = status.lower()
        terminal_states = ["running", "healthy", "done", "removed", "exited", "failed", "unhealthy"]
        if any(x in s_lower for x in terminal_states) and self.elapsed[item] is None:
            self.elapsed[item] = time.time() - self.times[item]
            changed = True
            
        self.statuses[item] = status
        if changed and redraw:
            request_render()

    def _render_lines(self) -> List[str]:
        lines = []
        for item in self.items:
            status = self.statuses[item]
            s_lower = status.lower()
            if any(x in s_lower for x in ["running", "healthy", "done", "removed"]):
                color = GREEN
            elif any(x in s_lower for x in ["starting", "pulling", "preparing", "terminating", "launching"]):
                color = ORANGE
            elif any(x in s_lower for x in ["restarting", "exited", "unhealthy", "failed"]):
                color = RED
            else:
                color = DIM
            curr_elapsed = self.elapsed[item] or (time.time() - self.times[item])
            time_str = f" {DIM}{curr_elapsed:.1f}s{END}"
            display_status = status
            if any(x in s_lower for x in ["launching", "preparing", "queued"]):
                display_status = ""
            tag = f"[{color}{display_status}{END}]" if display_status else f"[{DIM}      {END}]"
            lines.append(f"      {DIM}•{END} {ORANGE}{item}{END}: {tag}{time_str}")
        return lines


def log_step(step: int, total: int, message: str, bar: Optional[ProgressBar] = None):
    prefix = f"{PINK}{BOLD}[{step}/{total}]{END}"
    if bar: bar.update(step, message)
    else: safe_print(f"\n{prefix} {message}")
