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
import time
import uuid
from pathlib import Path

# --- Configuration ------------------------------------------------------------

SCAFFOLD_DIRS = [
    Path("media"),
    Path("media") / "movies",
    Path("media") / "tv",
    Path("downloads"),
    Path("logs"),
    Path("disk1"),
    Path("control-plane") / "state",
    Path("control-plane") / "config",
    Path("control-plane") / "state" / "health",
    Path("control-plane") / "state" / "locks",
]

# --- ANSI Colors --------------------------------------------------------------

GREEN = "\033[92m"
BLUE = "\033[94m"
CYAN = "\033[96m"
YELLOW = "\033[93m"
RED = "\033[91m"
BOLD = "\033[1m"
END = "\033[0m"

WARNINGS: list[str] = []
REPO_URL = "https://github.com/jakej985-rgb/M3tal-Media-Server.git"
PRESERVED_MERGE_PATHS = (
    Path(".env"),
    Path("dashboard") / "users.json",
    Path("control-plane") / "state",
    Path("control-plane") / "config",
)


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
    
    # Initialize ANSI support on Windows
    if system == "windows":
        os.system('')
        return "windows"
    
    if system == "darwin":
        return "macos"

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
    "python": {"check": "python --version" if platform.system().lower() == "windows" else "python3 --version", "debian": "sudo apt-get install -y python3 python3-pip", "fedora": "sudo dnf install -y python3 python3-pip", "arch": "sudo pacman -S --noconfirm python python-pip", "macos": "brew install python3"},
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


def ensure_directories(install_dir: Path, fix_perms: bool) -> None:
    """Creates the standard directory tree for M3TAL."""
    log(f"\n{BOLD}=== Directory Scaffolding ==={END}")
    
    for rel_path in SCAFFOLD_DIRS:
        abs_path = install_dir / rel_path
        if not abs_path.exists():
            log(f"  [CREATE] {rel_path}")
            abs_path.mkdir(parents=True, exist_ok=True)
        else:
            log(f"  [EXISTS] {rel_path}")
        
        if fix_perms and os.name != "nt":
            try:
                # Basic chown to current user
                import pwd
                user = pwd.getpwuid(os.getuid()).pw_name
                subprocess.run(["sudo", "chown", "-R", f"{user}:{user}", str(abs_path)], check=False)
            except (ImportError, AttributeError):
                pass


def setup_venv(install_dir: Path, venv_name: str) -> Path:
    """Creates a virtual environment and installs requirements."""
    log(f"\n{BOLD}=== Virtual Environment Setup ==={END}")
    venv_path = install_dir / venv_name
    
    if not venv_path.exists():
        log(f"  [CREATE] {venv_name}...")
        subprocess.run([sys.executable, "-m", "venv", str(venv_path)], check=True)
    else:
        log(f"  [EXISTS] {venv_name}")
    
    # Identify pip path
    pip_exe = venv_path / ("Scripts" if os.name == "nt" else "bin") / ("pip.exe" if os.name == "nt" else "pip")
    py_exe = venv_path / ("Scripts" if os.name == "nt" else "bin") / ("python.exe" if os.name == "nt" else "python")
    
    log(f"  [INSTALL] requirements.txt into {venv_name}...")
    req_file = install_dir / "requirements.txt"
    if req_file.exists():
        subprocess.run([str(pip_exe), "install", "-U", "pip"], check=False)
        subprocess.run([str(pip_exe), "install", "-r", str(req_file)], check=False)
    else:
        warn("requirements.txt missing — skipping pip install")
        
    return py_exe


# --- Repo Setup ---------------------------------------------------------------

def remove_path(path: Path) -> None:
    """Robust path removal that handles read-only files on Windows."""
    def on_error(func, path, exc_info):
        import stat
        try:
            os.chmod(path, stat.S_IWRITE)
            func(path)
        except:
            pass

    if path.is_dir():
        shutil.rmtree(path, onerror=on_error)
    else:
        try:
            if os.name == "nt": os.chmod(path, 0o777)
            path.unlink()
        except:
            pass


def create_staging_dir(parent_dir: Path, prefix: str) -> Path:
    base_dir = parent_dir if parent_dir.exists() else Path.cwd()
    while True:
        candidate = base_dir / f".{prefix}-{uuid.uuid4().hex[:8]}"
        try:
            candidate.mkdir(parents=True, exist_ok=False)
            return candidate
        except FileExistsError:
            continue


def merge_install_tree(source_dir: Path, install_dir: Path) -> None:
    preserve_stash = create_staging_dir(install_dir.parent, "m3tal-preserve")

    try:
        for relative_path in PRESERVED_MERGE_PATHS:
            src = install_dir / relative_path
            if not src.exists():
                continue

            stashed_path = preserve_stash / relative_path
            stashed_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src), str(stashed_path))

        for item in source_dir.iterdir():
            if item.name == ".git":
                continue

            dest = install_dir / item.name
            if dest.exists():
                remove_path(dest)

            if item.is_dir():
                shutil.copytree(item, dest)
            else:
                shutil.copy2(item, dest)

        for relative_path in PRESERVED_MERGE_PATHS:
            stashed_path = preserve_stash / relative_path
            if not stashed_path.exists():
                continue

            dest = install_dir / relative_path
            if dest.exists():
                remove_path(dest)

            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(stashed_path), str(dest))
    finally:
        remove_path(preserve_stash)


def is_valid_m3tal_repo(path: Path) -> bool:
    return (
        (path / "m3tal.py").exists() and
        (path / "control-plane").exists()
    )


def setup_repo(install_dir: Path, source_mode: str) -> bool:
    """Clone the repo or use local files, then move/merge to install_dir."""
    log(f"\n{BOLD}=== Repository Setup ==={END}")

    cwd = Path.cwd()

    # 🔥 LOCAL MODE
    if source_mode == "2":
        if not is_valid_m3tal_repo(cwd):
            log(f"{RED}[ERROR] Current directory is not a valid M3TAL repo{END}")
            return False

        log("[LOCAL] Using current directory as source")

        if install_dir.resolve() == cwd.resolve():
            log("[OK] Using current directory directly")
            return True

        if install_dir.exists() and any(install_dir.iterdir()):
            log(f"{RED}[ERROR] Target directory not empty: {install_dir}{END}")
            return False

        log(f"[COPY] {cwd} → {install_dir}")
        shutil.copytree(cwd, install_dir, dirs_exist_ok=True)
        return True

    # 🔥 CLONE MODE
    if install_dir.exists():
        log(f"\nInstall directory exists: {install_dir}")
        log("  1) Merge (safe — preserves .env, users, state, and config)")
        log("  2) Replace (fresh install)")
        log("  3) Cancel")
        action = ask("Select", "1")

        if action == "1":
            log("[MERGE] Updating install...")
            tmp_dir = create_staging_dir(install_dir.parent, "m3tal-clone")
            try:
                subprocess.run(["git", "clone", REPO_URL, str(tmp_dir)], check=True)
                merge_install_tree(tmp_dir, install_dir)
            except subprocess.CalledProcessError:
                log(f"{RED}[ERROR] Clone failed{END}")
                return False
            finally:
                remove_path(tmp_dir)
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
    start_time = time.time()
    print(f"\n{BOLD}{BLUE}=== M3TAL MEDIA SERVER INTERACTIVE INSTALL ==={END}\n")

    os_type = detect_os()
    log(f"Detected OS: {BOLD}{os_type}{END}")

    # Config wizard
    working_dir = Path.cwd()
    
    if is_valid_m3tal_repo(working_dir):
        default_source = "2"
        default_dir = str(working_dir)
    else:
        default_source = "1"
        default_dir = str(Path.home() / "M3tal-Media-Server")
        
    source_mode = ask("Installation source (1=clone / 2=local)", default_source).lower()
    install_dir = Path(ask("Install directory", default_dir))
    venv_name = ask("Virtual environment name", "venv")
    auto_install = ask("Auto-install missing dependencies? (y/n)", "y").lower() == "y"
    fix_perms = ask("Fix permissions for data directories? (y/n)", "y").lower() == "y"
    auto_start = ask("Start system after install? (y/n)", "n").lower() == "y"

    log(f"\n{BOLD}=== Summary ==={END}")
    log(f"  Install Dir:  {install_dir}")
    log(f"  Venv Name:    {venv_name}")
    log(f"  Fix Perms:    {fix_perms}")
    log(f"  Auto Install: {auto_install}")
    log(f"  Auto Start:   {auto_start}")

    confirm = ask("\nProceed? (y/n)", "y")
    if confirm.lower() != "y":
        sys.exit(1)

    # 1. Dependencies
    check_and_install_deps(os_type, auto_install)

    # 2. Repository
    if not setup_repo(install_dir, source_mode):
        sys.exit(1)

    os.chdir(install_dir)

    # 3. Virtual Environment
    venv_python = setup_venv(install_dir, venv_name)

    # 4. Scaffolding
    ensure_directories(install_dir, fix_perms)

    # 5. Environment config
    log(f"\n{BOLD}=== Environment Configuration ==={END}")
    wizard = install_dir / "scripts" / "config" / "configure_env.py"
    if wizard.exists():
        subprocess.run([str(venv_python), str(wizard)], check=True)
    else:
        warn("Configuration wizard missing (checked scripts/config/configure_env.py)")
        env_example = install_dir / ".env.example"
        if env_example.exists():
            shutil.copy2(env_example, install_dir / ".env")





    # 7. Docker network
    log(f"\n{BOLD}=== Docker Network ==={END}")
    try:
        should_prune = ask("Prune existing 'proxy' network before creation? (y/n)", "n").lower() == "y"
        if should_prune:
            subprocess.run(["docker", "network", "rm", "proxy"], check=False)
            
        result = subprocess.run(["docker", "network", "ls"], capture_output=True, text=True)
        if "proxy" in result.stdout and not should_prune:
            log(f"  {GREEN}[OK]{END} network exists")
        else:
            subprocess.run(["docker", "network", "create", "proxy"], check=True)
            log(f"  {GREEN}[CREATED]{END} proxy network")
    except FileNotFoundError:
        warn("Docker not available — network not created")

    # 8. Final checks
    log(f"\n{BOLD}=== Final Checks ==={END}")
    for cmd_label, cmd_args in [("Docker", ["docker", "--version"]), ("Python (Venv)", [str(venv_python), "--version"])]:
        try:
            subprocess.run(cmd_args, capture_output=True, text=True)
            log(f"  {GREEN}[OK]{END} {cmd_label}")
        except FileNotFoundError:
            warn(f"{cmd_label} not found")



    # 9. Auto-start
    if auto_start:
        log(f"\n{BOLD}[START] Launching control plane...{END}")
        m3tal_cli = install_dir / "m3tal.py"
        subprocess.Popen([str(venv_python), str(m3tal_cli), "init"])

    # 10. Warnings summary
    if WARNINGS:
        log(f"\n{YELLOW}{BOLD}=== WARNINGS ==={END}")
        for w in WARNINGS:
            log(f"  - {w}")
        log(f"  ⚠️  Some dependencies may need manual installation")

    # 10. Done
    duration = time.time() - start_time
    log(f"\n{GREEN}{BOLD}=== INSTALL COMPLETE ==={END}")
    log(f"  Total Time:   {duration:.2f}s\n")
    
    if auto_start:
        log(f"  m3tal media server started, use m3tal.py to start")
    else:
        log(f"  m3tal media server not started, use m3tal.py to start")
        
    log(f"  Dashboard will be at:     http://localhost:8080\n")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n{YELLOW}Installation interrupted by user.{END}")
    except SystemExit:
        # Catch sys.exit() calls so the finally-style pause still runs
        pass
    except Exception as e:
        print(f"\n{RED}FATAL ERROR: {e}{END}")
    
    print(f"\n{BOLD}Installation process finished.{END}")
    input(f"\n{CYAN}Press Enter to close this window...{END}")
    sys.exit(0)
