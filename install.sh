#!/bin/bash
# M3TAL Media Server — Linux Bootstrap Script
# v2.0.0 — Refactored to hand off to install.py

set -e

GREEN="\033[92m"
YELLOW="\033[93m"
BOLD="\033[1m"
END="\033[0m"

log() { echo -e "${GREEN}[INFO]${END} $1"; }
warn() { echo -e "${YELLOW}[WARN]${END} $1"; }

check_cmd() { command -v "$1" >/dev/null 2>&1; }

echo -e "${BOLD}=== M3TAL Media Server Installer (Linux Bootstrap) ===${END}"

# 1. Distribution Detection
if [ -f /etc/os-release ]; then
    . /etc/os-release
    OS=$ID
else
    OS=$(uname -s | tr '[:upper:]' '[:lower:]')
fi

log "Detected OS: ${OS}"

# 2. Base Dependency Check (Python & Git)
log "Ensuring Python 3 and Git are present..."

case $OS in
    ubuntu|debian|raspbian)
        sudo apt-get update -y
        sudo apt-get install -y python3 python3-pip python3-venv git curl
        ;;
    fedora|rhel|centos)
        sudo dnf install -y python3 python3-pip git curl
        ;;
    arch)
        sudo pacman -S --noconfirm python python-pip git curl
        ;;
    *)
        warn "Unsupported or unknown distribution ($OS). Please ensure python3, pip, and venv are installed manually."
        ;;
esac

# 3. Hand off to install.py
if [ -f "install.py" ]; then
    log "Bootstrapping complete. Launching M3TAL Interactive Installer..."
    python3 install.py "$@"
else
    # If install.py isn't here, we might need to clone first or we're in a weird state
    warn "install.py not found in current directory."
    read -p "Would you like to clone M3TAL Media Server now? (y/n) " CLONE
    if [ "$CLONE" == "y" ]; then
        git clone https://github.com/jakej985-rgb/M3tal-Media-Server.git
        cd M3tal-Media-Server
        python3 install.py "$@"
    else
        echo "Exiting."
        exit 1
    fi
fi
