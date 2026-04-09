# 📗 Getting Started with M3TAL

Welcome to **M3TAL Media Server**! This guide will help you get your autonomous media server running in 10 minutes, even if you are new to Linux or Docker.

---

## 🏗️ What is M3TAL?

Think of M3TAL as your server's **robot brain**. Instead of you checking every day if your movies are downloading or if a container has crashed, M3TAL's "Agents" watch the server for you 24/7 and fix problems automatically.

---

## 🛠️ Step 1: Preparation

You will need a Linux server (Ubuntu is recommended) and basic command line access (SSH).

### 1. Update your system

Before starting, ensure your server is up to date:

```bash
sudo apt update && sudo apt upgrade -y
```

### 2. Download M3TAL

Clone the repository to your server:

```bash
git clone https://github.com/jakej985-rgb/M3tal-Media-Server.git
cd M3tal-Media-Server
```

---

## 🚀 Step 2: Installation

M3TAL comes with an **Interactive Setup Wizard** that installs everything for you (Docker, Python, and all agents).

1. **Run the installer**:

   ```bash
   chmod +x install.sh
   ./install.sh
   ```

2. **Follow the Prompts**:

   * **Data Directory**: Typically `/mnt`. This is where your movies and shows will live.
   * **Auto-Install**: Type `y` to let M3TAL install Docker for you.
   * **Auto-Start**: Type `y` to launch the dashboard immediately.

---

## 🖥️ Step 3: The Dashboard

Once installed, M3TAL provides a web interface to see what's happening.

1. **Open your browser** and go to `http://YOUR_SERVER_IP:8080`.

2. **Log in** with the admin credentials you created during setup:

   * **Username**: `admin`
   * **Password**: the admin password you chose during the interactive setup

3. **Recover or rotate your password if needed**: Run `python scripts/manage_users.py --reset-admin` from an interactive terminal.

---

## 办 Step 4: Adding Your Services

M3TAL looks inside the `docker/` folder for your apps.

1. **Explore the folders**: Inside `docker/media/`, you will find a `docker-compose.yml`. This file defines apps like Radarr (Movies) and Sonarr (TV).

2. **Customizing**: You can edit these files to add your own apps. M3TAL will automatically detect them and start monitoring them within 60 seconds.

---

## 🚑 Step 5: Self-Healing in Action

You don't need to do anything! If a container crashes:

1. The **Monitor** will see it's offline.
2. The **Decision Engine** will plan a restart.
3. The **Reconciler** will bring it back to life.
4. You can check the **Logs** tab in the dashboard to see exactly when and why M3TAL fixed the issue.

---

## 💾 Step 6: Backups

To keep your configuration safe, run the backup script once a week:

```bash
bash scripts/backup.sh
```

This saves your settings to `/mnt/backups`. If anything breaks, you can use `bash scripts/restore.sh` to get everything back.

---

## 💡 Pro Tips for Beginners

* **Paths**: Always use `/mnt` for your hard drives. M3TAL expects this structure to keep your media organized.
* **Logs**: If something isn't working, check `control-plane/state/logs/`. Every agent leaves a detailed trail of what it's thinking.
* **Resources**: Use the Dashboard's "Metrics" tab to see which app is using too much RAM or CPU.

---

**Welcome to the future of homelabbing!** 🚀

If you have questions, check the [Full Documentation](docs/) or open an issue on GitHub.
