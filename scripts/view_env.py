import os
import sys
from pathlib import Path

# M3TAL Environment Audit Tool (v2.2 Hardened)
# Responsibility: Safely inspect environment variables with secret masking.

def find_root():
    """Auto-detect repo root by walking up parents."""
    p = Path(__file__).resolve()
    for parent in [p] + list(p.parents):
        if (parent / ".env").exists() and (parent / "docker").exists():
            return parent
    return None

ROOT = find_root()
ENV_FILE = ROOT / ".env" if ROOT else None

SENSITIVE_KEYS = ["TOKEN", "SECRET", "KEY", "PASSWORD"]

def mask(val: str) -> str:
    """Reveals only a safe preview of sensitive values."""
    if not val:
        return ""
    if len(val) <= 4:
        return "***"
    # Reveal first 2 and last 2 characters
    return val[:2] + "***" + val[-2:]

def load_env_safe():
    """Hardened .env parser that handles comments, blank lines, and quotes."""
    env = {}
    if not ENV_FILE or not ENV_FILE.exists():
        return env
    
    try:
        with open(ENV_FILE, "r") as f:
            for line in f:
                line = line.strip()
                # Skip comments and blank lines
                if not line or line.startswith("#"):
                    continue
                # Skip lines without assignment
                if "=" not in line:
                    continue
                
                # Handle 'export VAR=val' format
                if line.startswith("export "):
                    line = line[len("export "):].strip()
                
                k, v = line.split("=", 1)
                # Aggressive strip for CRLF and whitespace
                k = k.strip()
                v = v.strip().strip('"').strip("'")
                
                env[k] = v
    except Exception as e:
        print(f"⚠️  Warning: Error reading .env: {e}")
        
    return env

def main():
    if not ROOT:
        print("❌ ERROR: Could not locate repository root (missing .env or docker/)")
        sys.exit(1)
        
    env = load_env_safe()
    
    print("=" * 60)
    print("M3TAL ENVIRONMENT AUDIT TOOL")
    print(f"   Root: {ROOT}")
    print(f"   Env:  {ENV_FILE}")
    print("=" * 60)
    
    if not env:
        print("   [!] No variables found in .env file.")
    else:
        for k in sorted(env.keys()):
            v = env[k]
            # Detect sensitive keys for masking
            if any(s in k.upper() for s in SENSITIVE_KEYS):
                print(f"  {k:25} = {mask(v)}")
            else:
                print(f"  {k:25} = {v}")
            
    print("=" * 60)

if __name__ == "__main__":
    main()
