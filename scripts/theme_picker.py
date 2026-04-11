#!/usr/bin/env python3
import json
import os
import sys
import tkinter as tk
from tkinter import colorchooser, messagebox
from pathlib import Path

# --- Context ------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent # Root
THEME_FILE = BASE_DIR / "control-plane" / "state" / "theme.json"

def hex_to_rgb(hex_str: str):
    """Converts #RRGGBB to (R, G, B)."""
    hex_str = hex_str.lstrip('#')
    return list(int(hex_str[i:i+2], 16) for i in (0, 2, 4))

def save_theme(primary_hex: str, secondary_hex: str):
    """Saves colors to theme.json."""
    data = {
        "primary": {
            "hex": primary_hex,
            "rgb": hex_to_rgb(primary_hex)
        },
        "secondary": {
            "hex": secondary_hex,
            "rgb": hex_to_rgb(secondary_hex)
        }
    }
    
    # Ensure dir exists
    THEME_FILE.parent.mkdir(parents=True, exist_ok=True)
    
    with open(THEME_FILE, 'w') as f:
        json.dump(data, f, indent=4)
    
    print(f"\n[THEME] Saved globally: {primary_hex} & {secondary_hex}")
    
    # Terminal Preview
    p = data["primary"]["rgb"]
    s = data["secondary"]["rgb"]
    pink = f"\033[38;2;{p[0]};{p[1]};{p[2]}m"
    orange = f"\033[38;2;{s[0]};{s[1]};{s[2]}m"
    end = "\033[0m"
    bold = "\033[1m"
    
    print(f"\n{pink}{bold}============================================================{end}")
    print(f"{pink}{bold}  M3TAL THEME PREVIEW — NEON ACTIVATED{end}")
    print(f"{pink}{bold}============================================================{end}")
    print(f"  {orange}• Primary Accent (Pink replacement): {pink}██████████{end}")
    print(f"  {orange}• Secondary Accent (Orange replacement): {orange}██████████{end}")
    print(f"{pink}{bold}============================================================{end}\n")

def run_picker():
    root = tk.Tk()
    root.withdraw() # Hide main win
    
    messagebox.showinfo("M3TAL Theme Picker", "Step 1: Choose your Primary Accent (Pink)")
    p_color = colorchooser.askcolor(color="#FF13F0", title="Choose Primary Neon Pink")
    
    if not p_color[1]: 
        print("Cancelled.")
        return

    messagebox.showinfo("M3TAL Theme Picker", "Step 2: Choose your Secondary Accent (Orange)")
    s_color = colorchooser.askcolor(color="#FFA500", title="Choose Secondary Neon Orange")
    
    if not s_color[1]:
        print("Cancelled.")
        return

    save_theme(p_color[1], s_color[1])
    messagebox.showinfo("M3TAL Theme Picker", "Theme saved! Restart M3TAL to see the new neon.")
    root.destroy()

if __name__ == "__main__":
    try:
        run_picker()
    except Exception as e:
        print(f"Theme Picker Error: {e}")
        # Fallback for headless or missing Tk
        if "no display name" in str(e).lower():
            print("\n[ERROR] Display not found. Are you in a remote SSH session?")
