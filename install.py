#!/usr/bin/env python3
"""
M3TAL Media Server — Cross-Platform Interactive Installer
v1.3.0 — Python replacement for install.sh

Detects OS, checks/installs dependencies, clones the repo,
runs init.py, and launches configure_env.py.

Works on: Ubuntu/Debian, Fedora/RHEL, Arch, macOS, Windows/WSL2
"""

import os
import platform
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

# --- ANSI Colors --------------------------------------------------------------

GREEN = "\033[92m"
BLUE = "\033[94m"
YELLOW = "\033[93m"
RED = "\033[91m"
BOLD = "\033[1m"
END = "\033[0m"

WARNINGS: list[str] = []
REPO_URL = "https://github.com/jakej985-rgb/M3tal-Media-Server.git"


def log(msg: str) -> None:
    print(f"{msg}")


def warn(msg: str) -> None:
    WARNINGS.append(msg)
    print(f"{YELLOW}[WARN] {msg}{END}")


def ask(prompt: str, default: str = "") -> str:
    display = f"{prompt} [{YELLOW}{default}{END}]: " if default else f"{prompt}: "
    answer = input(display).strip()
    return answer if answer else default


# --- OS Detection -------------------------------------------------------------

def detect_os() -> str:
    """Detect the host operating system family."""
    system = platform.system().lower()
    if system == "darwin":
        return "macos"
    if system == "windows":
        return "windows"

    # Linux — detect distro
    try:
        with open("/etc/os-release") as f:
            content = f.read().lower()
        if "ubuntu" in content or "debian" in content:
            return "debian"
        if "fedora" in content or "rhel" in content or "centos" in content:
            return "fedora"
        if "arch" in content:
            return "arch"
    except FileNotFoundError:
        pass

    return "linux"  # Generic fallback


# --- Dependency Checking -----------------------------------------------------

DEPS = {
    "git":    {"check": "git --version",    "debian": "sudo apt-get install -y git",      "fedora": "sudo dnf install -y git",       "arch": "sudo pacman -S --noconfirm git",    "macos": "brew install git"},
    "docker": {"check": "docker --version", "debian": "curl -fsSL https://get.docker.com | sh", "fedora": "curl -fsSL https://get.docker.com | sh", "arch": "sudo pacman -S --noconfirm docker", "macos": "brew install --cask docker"},
    "python3": {"check": "python3 --version", "debian": "sudo apt-get install -y python3 python3-pip", "fedora": "sudo dnf install -y python3 python3-pip", "arch": "sudo pacman -S --noconfirm python python-pip", "macos": "brew install python3"},
    "docker compose": {"check": "docker compose version", "debian": "sudo apt-get install -y docker-compose-plugin", "fedora": "sudo dnf install -y docker-compose-plugin", "arch": "sudo pacman -S --noconfirm docker-compose", "macos": "echo 'Docker Desktop includes Compose'"},
}


def check_cmd(cmd: str) -> bool:
    try:
        subprocess.run(cmd.split(), capture_output=True, timeout=10)
        return True
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def check_and_install_deps(os_type: str, auto_install: bool) -> None:
    log(f"\n{BOLD}=== Checking Dependencies ==={END}")

    for name, info in DEPS.items():
        if check_cmd(info["check"]):
            log(f"  {GREEN}[OK]{END} {name}")
        else:
            if auto_install and os_type in info:
                log(f"  {YELLOW}[INSTALLING]{END} {name}")
                try:
                    subprocess.run(info[os_type], shell=True, check=True)
                except subprocess.CalledProcessError:
                    warn(f"Failed to install {name}")
            else:
                warn(f"{name} not found — install manually")


# --- Repo Setup ---------------------------------------------------------------

def setup_repo(install_dir: Path) -> bool:
    """Clone the repo into a temp dir, then move/merge into install_dir."""
    log(f"\n{BOLD}=== Repository Setup ==={END}")

    if install_dir.exists():
        log(f"\nInstall directory exists: {install_dir}")
        log("  1) Merge (safe — preserves .env and state)")
        log("  2) Replace (fresh install)")
        log("  3) Cancel")
        action = ask("Select", "1")

        if action == "1":
            log("[MERGE] Updating install...")
            tmp_dir = Path(tempfile.mkdtemp(prefix="m3tal-"))
            subprocess.run(["git", "clone", REPO_URL, str(tmp_dir)], check=True)
            # Copy new files, skip .env and state
            for item in tmp_dir.iterdir():
                dest = install_dir / item.name
                if item.name in (".env", "control-plane"):
                    continue  # Preserve user config and state
                if item.is_dir():
                    if dest.exists():
                        shutil.rmtree(dest)
                    shutil.copytree(item, dest)
                else:
                    shutil.copy2(item, dest)
            shutil.rmtree(tmp_dir)
            return True

        elif action == "2":
            backup_name = f"{install_dir.name}-backup-{int(__import__('time').time())}"
            backup_path = install_dir.parent / backup_name
            log(f"[BACKUP] {backup_path}")
            install_dir.rename(backup_path)
        else:
            log("Cancelled.")
            return False

    log(f"[CLONE] Cloning into {install_dir}...")
    try:
        subprocess.run(["git", "clone", REPO_URL, str(install_dir)], check=True)
        return True
    except subprocess.CalledProcessError:
        log(f"{RED}[ERROR] Clone failed{END}")
        return False


# --- Main ---------------------------------------------------------------------

def main() -> None:
    print(f"\n{BOLD}{BLUE}=== M3TAL MEDIA SERVER INTERACTIVE INSTALL ==={END}\n")

    os_type = detect_os()
    log(f"Detected OS: {BOLD}{os_type}{END}")

    # Config wizard
    default_dir = str(Path.home() / "M3tal-Media-Server")
    install_dir = Path(ask("Install directory", default_dir))
    auto_install = ask("Auto-install missing dependencies? (y/n)", "y").lower() == "y"
    auto_start = ask("Start system after install? (y/n)", "y").lower() == "y"

    log(f"\n{BOLD}=== Summary ==={END}")
    log(f"  Install Dir:  {install_dir}")
    log(f"  Auto Install: {auto_install}")
    log(f"  Auto Start:   {auto_start}")

    confirm = ask("\nProceed? (y/n)", "y")
    if confirm.lower() != "y":
        sys.exit(1)

    # 1. Dependencies
    check_and_install_deps(os_type, auto_install)

    # 2. Python packages
    log(f"\n{BOLD}=== Installing Python Dependencies ==={END}")
    req_file = Path("requirements.txt")
    if req_file.exists():
        subprocess.run([sys.executable, "-m", "pip", "install", "-r", str(req_file)], check=False)
    else:
        warn("requirements.txt not found — skip pip install")

    # 3. Repository
    if not setup_repo(install_dir):
        sys.exit(1)

    os.chdir(install_dir)

    # 4. Init
    log(f"\n{BOLD}=== Initializing M3TAL Control Plane ==={END}")
    init_script = install_dir / "control-plane" / "init.py"
    subprocess.run([sys.executable, str(init_script)], check=True)

    # 5. Environment config
    log(f"\n{BOLD}=== Environment Configuration ==={END}")
    wizard = install_dir / "scripts" / "configure_env.py"
    if wizard.exists():
        subprocess.run([sys.executable, str(wizard)], check=True)
    else:
        warn("Configuration wizard missing, using .env.example")
        env_example = install_dir / ".env.example"
        if env_example.exists():
            shutil.copy2(env_example, install_dir / ".env")

    # 6. Docker network
    log(f"\n{BOLD}=== Docker Network ==={END}")
    try:
        result = subprocess.run(["docker", "network", "ls"], capture_output=True, text=True)
        if "m3tal" in result.stdout:
            log(f"  {GREEN}[OK]{END} network exists")
        else:
            subprocess.run(["docker", "network", "create", "m3tal"], check=True)
            log(f"  {GREEN}[CREATED]{END} m3tal network")
    except FileNotFoundError:
        warn("Docker not available — network not created")

    # 7. Final checks
    log(f"\n{BOLD}=== Final Checks ==={END}")
    for cmd in ["docker --version", "python3 --version"]:
        try:
            result = subprocess.run(cmd.split(), capture_output=True, text=True)
            log(f"  {GREEN}[OK]{END} {result.stdout.strip()}")
        except FileNotFoundError:
            warn(f"{cmd.split()[0]} not found")

    # 8. Auto-start
    if auto_start:
        log(f"\n{BOLD}[START] Launching control plane...{END}")
        supervisor = install_dir / "control-plane" / "supervisor.py"
        subprocess.Popen([sys.executable, str(supervisor)])

    # 9. Warnings summary
    if WARNINGS:
        log(f"\n{YELLOW}{BOLD}=== WARNINGS ==={END}")
        for w in WARNINGS:
            log(f"  - {w}")
        log(f"  ⚠️  Some dependencies may need manual installation")

    # 10. Done
    log(f"\n{GREEN}{BOLD}=== INSTALL COMPLETE ==={END}")
    log(f"\n  Run manually: python3 control-plane/supervisor.py")
    log(f"  Dashboard:    http://localhost:8080\n")


if __name__ == "__main__":
    main()
