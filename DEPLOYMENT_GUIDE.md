# Cloud Deployment Guide - Gold Trading Bot

This guide explains how to run your trading bot 24/7 on a Cloud VPS (Virtual Private Server) for free.

## 1. Choosing a Free Cloud Provider

| Provider | Plan Name | Duration | Best For |
| :--- | :--- | :--- | :--- |
| **Oracle Cloud** | Always Free | **Lifetime** | Most powerful, permanent free tier. |
| **Google Cloud** | e2-micro | **Lifetime** | Highly reliable, though lower RAM. |
| **AWS** | Free Tier | 12 Months | Industry standard, but expires after a year. |

**Recommendation:** Use **Oracle Cloud** (Ubuntu 22.04) for its permanent "Always Free" status.

---

## 2. Server Setup (Ubuntu Linux)

Once you have created your instance and SSH'd into it, run the following commands:

### A. Update System & Install Python
```bash
sudo apt update && sudo apt upgrade -y
sudo apt install python3-pip python3-venv git -y
```

### B. Clone Your Code
```bash
git clone <your-repository-url>
cd GOLD
```

### C. Set Up Virtual Environment
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

---

## 2. Security: Environment Variables

**CRITICAL**: Do not keep your `UPSTOX_ACCESS_TOKEN` inside `config.py` on a cloud server.

1.  Create an `.env` file: `nano .env`
2.  Add your secrets:
    ```env
    UPSTOX_ACCESS_TOKEN=your_token_here
    ```
3.  Add `.env` to your `.gitignore` if it's not already there.

---

## 3. Running the Bot 24/7 (Persistence)

If you just run `python main.py`, it will stop when you close your terminal. Use one of these methods to keep it alive:

### Option A: Using `screen` (Simplest)
1.  **Start session**: `screen -S gold_bot`
2.  **Run bot**: `python main.py`
3.  **Detach**: Press `Ctrl + A` then `D`. (You can now safely close your PC).
4.  **Reattach later**: `screen -r gold_bot`

### Option B: Using `systemd` (Professional)
This ensures the bot **auto-restarts** if the server reboots.

1.  Create a service file: `sudo nano /etc/systemd/system/gold.service`
2.  Paste this configuration (adjust paths):
    ```ini
    [Unit]
    Description=Gold Trading Bot
    After=network.target

    [Service]
    User=ubuntu
    WorkingDirectory=/home/ubuntu/GOLD
    ExecStart=/home/ubuntu/GOLD/venv/bin/python main.py
    Restart=always

    [Install]
    WantedBy=multi-user.target
    ```
3.  **Start service**:
    ```bash
    sudo systemctl daemon-reload
    sudo systemctl enable gold.service
    sudo systemctl start gold.service
    ```
4.  **Check status**: `sudo systemctl status gold.service`

---

## 4. Monitoring Logs
On the cloud, you can check your logs anytime:
- **If using screen**: Reattach with `screen -r gold_bot`.
- **If using systemd**: Use `journalctl -u gold.service -f`.
- **Internal Logs**: Check the `Logs/` directory created by the bot.
