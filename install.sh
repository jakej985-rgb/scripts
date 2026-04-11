#!/bin/bash

set -e

LOG="install.log"
WARNINGS=()

echo "=== M3TAL MEDIA SERVER INTERACTIVE INSTALL ===" | tee $LOG

# -------------------------------
# Helpers
# -------------------------------

check_cmd() { command -v "$1" >/dev/null 2>&1; }

ask() {
  local prompt=$1
  local default=$2
  read -p "$prompt [$default]: " input
  echo "${input:-$default}"
}

log() { echo "$1" | tee -a $LOG; }
warn() { WARNINGS+=("$1"); echo "[WARN] $1" | tee -a $LOG; }

# -------------------------------
# CONFIG WIZARD
# -------------------------------

echo ""
echo "=== Configuration Wizard ==="

INSTALL_DIR=$(ask "Install directory" "$HOME/M3tal-Media-Server")
AUTO_INSTALL=$(ask "Auto-install missing dependencies? (y/n)" "y")
AUTO_START=$(ask "Start system after install? (y/n)" "y")

echo ""
echo "=== Summary ==="
echo "Install Dir: $INSTALL_DIR"
echo "Auto Install: $AUTO_INSTALL"
echo "Auto Start: $AUTO_START"
echo ""

read -p "Proceed? (y/n): " CONFIRM
[ "$CONFIRM" != "y" ] && exit 1

# -------------------------------
# DEPENDENCIES (SAFE)
# -------------------------------

echo ""
log "=== Checking dependencies ==="

check_and_install() {
  local name=$1
  local check=$2
  local install=$3

  if eval "$check"; then
    log "[OK] $name"
  else
    log "[MISSING] $name"
    if [[ "$AUTO_INSTALL" == "y" ]]; then
      log "[INSTALL] $name"
      eval "$install"
    else
      warn "$name not installed"
    fi
  fi
}

# Only run apt-get on Debian/Ubuntu (Audit fix 3.5)
if command -v apt-get >/dev/null 2>&1; then
  sudo apt-get update -y
fi

check_and_install "git" "check_cmd git" "sudo apt-get install -y git"
check_and_install "curl" "check_cmd curl" "sudo apt-get install -y curl"

check_and_install "docker" "check_cmd docker" \
"curl -fsSL https://get.docker.com | sh && sudo usermod -aG docker $USER"

check_and_install "docker compose" \
"docker compose version >/dev/null 2>&1 || check_cmd docker-compose" \
"sudo apt-get install -y docker-compose-plugin"

check_and_install "python3" "check_cmd python3" "sudo apt-get install -y python3"
check_and_install "pip3" "check_cmd pip3" "sudo apt-get install -y python3-pip"
check_and_install "jq" "check_cmd jq" "sudo apt-get install -y jq"
check_and_install "yq" "check_cmd yq" "sudo wget https://github.com/mikefarah/yq/releases/latest/download/yq_linux_amd64 -O /usr/local/bin/yq && sudo chmod +x /usr/local/bin/yq"

# -------------------------------
# PYTHON DEPENDENCIES
# -------------------------------
log "=== Installing Python dependencies ==="
if [ -f "requirements.txt" ]; then
  pip3 install -r requirements.txt || warn "pip install failed"
else
  # Fallback for old versions or manual runs
  pip3 install Flask Flask-SocketIO requests bcrypt PyYAML eventlet || warn "pip install failed"
fi

# -------------------------------
# TEMP CLONE
# -------------------------------

echo ""
log "=== Repository Setup (safe temp clone) ==="

TMP_DIR=$(mktemp -d -t m3tal-install-XXXX)
REPO_URL="https://github.com/jakej985-rgb/M3tal-Media-Server.git"

log "[TEMP] Cloning into $TMP_DIR"

if git clone "$REPO_URL" "$TMP_DIR"; then
  log "[OK] Repo cloned"
else
  echo "[ERROR] Clone failed"
  rm -rf "$TMP_DIR"
  exit 1
fi

# -------------------------------
# HANDLE EXISTING INSTALL
# -------------------------------

if [ -d "$INSTALL_DIR" ]; then
  echo ""
  echo "Install directory exists: $INSTALL_DIR"
  echo "1) Merge (safe)"
  echo "2) Replace (fresh install)"
  echo "3) Cancel"

  read -p "Select [1/2/3]: " ACTION

  case $ACTION in
    1)
      log "[MERGE] Updating install"
      rsync -a \
        --exclude '.env' \
        --exclude 'dashboard/users.json' \
        --exclude 'control-plane/state' \
        --exclude 'control-plane/config' \
        "$TMP_DIR"/ "$INSTALL_DIR"/
      ;;
    2)
      BACKUP_DIR="$INSTALL_DIR-backup-$(date +%s)"
      log "[BACKUP] $BACKUP_DIR"
      mv "$INSTALL_DIR" "$BACKUP_DIR"
      mv "$TMP_DIR" "$INSTALL_DIR"
      TMP_DIR=""
      ;;
    *)
      echo "Cancelled."
      rm -rf "$TMP_DIR"
      exit 1
      ;;
  esac
else
  log "[MOVE] Fresh install"
  mv "$TMP_DIR" "$INSTALL_DIR"
  TMP_DIR=""
fi

[ -n "$TMP_DIR" ] && rm -rf "$TMP_DIR"

cd "$INSTALL_DIR"

# -------------------------------
# CONFIG
# -------------------------------

# -------------------------------
# CONFIG & INITIALIZATION
# -------------------------------

echo ""
log "=== Initializing M3TAL Control Plane ==="

# Delegate scaffolding to the unified init script
bash control-plane/init.sh | tee -a $LOG

echo ""
log "=== Environment Configuration ==="
# Use the new interactive Python wizard instead of manual sed patching
if [ -f "scripts/config/configure_env.py" ]; then
  python3 scripts/config/configure_env.py
else
  warn "Configuration wizard missing, using .env.example"
  cp .env.example .env
fi

# -------------------------------
# DOCKER NETWORK
# -------------------------------

if docker network ls | grep -q m3tal; then
  log "[OK] network exists"
else
  log "[CREATE] docker network"
  docker network create m3tal
fi

# -------------------------------
# PERMISSIONS
# -------------------------------

sudo chown -R $USER:$USER "$INSTALL_DIR"

# -------------------------------
# DOMAIN PATCH
# -------------------------------

log "=== Applying domain config ==="
# Set REPO_ROOT and source .env for DOMAIN (Audit fix 3.4)
REPO_ROOT="$INSTALL_DIR"
source "$INSTALL_DIR/.env" 2>/dev/null || true
if [ -n "$DOMAIN" ] && [ "$DOMAIN" != "local" ]; then
  # Recursive find to catch multi-stack architecture (Batch 14 T2)
  find "$REPO_ROOT/docker" -type f -name "*.yml" -exec sed -i "s/\.local/.$DOMAIN/g" {} \;
fi

# -------------------------------
# FINAL CHECK
# -------------------------------

echo ""
log "=== Final Checks ==="

docker --version || warn "docker issue"
python3 --version || warn "python issue"

if docker compose version >/dev/null 2>&1; then
  docker compose version | tee -a $LOG
else
  warn "docker compose missing"
fi

# -------------------------------
# AUTO START
# -------------------------------

if [ "$AUTO_START" == "y" ]; then
  echo ""
  log "[START] Control plane"
  bash control-plane/run.sh &
fi

# -------------------------------
# WARNINGS
# -------------------------------

if [ ${#WARNINGS[@]} -ne 0 ]; then
  echo ""
  echo "=== WARNINGS ==="
  for w in "${WARNINGS[@]}"; do
    echo "- $w"
  done
  echo "⚠️ Some dependencies may need manual upgrade"
fi

# -------------------------------
# DONE
# -------------------------------

echo ""
echo "=== INSTALL COMPLETE ==="
echo ""
echo "Access:"
echo "Traefik: http://localhost:8080"
echo "Apps: http://radarr.$DOMAIN"
echo ""
echo "Run manually:"
echo "bash control-plane/run.sh"
echo ""
echo "⚠️ If docker permission issues:"
echo "newgrp docker"
