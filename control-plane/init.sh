#!/bin/bash
# init.sh — Thin shim for backward compatibility
# All logic now lives in init.py (v1.3.0)

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec python3 "$SCRIPT_DIR/init.py" "$@"