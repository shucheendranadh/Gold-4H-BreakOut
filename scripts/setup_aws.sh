#!/bin/bash
# setup_aws.sh — Idempotent setup for GOLD 4H Breakout Bot on AWS Linux.
# Called by the GitHub Actions deploy pipeline on every push.
# Safe to run multiple times: system packages only install on first run.
#
# Token is read from ~/tradingbridge/.token.env (hardcoded in config.py).
# That file must be created manually on the server — never committed to git.
#
# Usage:
#   sudo bash setup_aws.sh --project /home/ubuntu/gold-bot --user ubuntu

set -e

TOKEN_FILE_PATH_HARDCODED="\$HOME/tradingbridge/.token.env"

# ── Parse arguments ────────────────────────────────────────────────────────────
PROJECT_LOCATION=""
RUN_USER=""

while [[ "$#" -gt 0 ]]; do
    case $1 in
        --project) PROJECT_LOCATION="$2"; shift ;;
        --user)    RUN_USER="$2";         shift ;;
        *) echo "Unknown argument: $1"; exit 1 ;;
    esac
    shift
done

if [[ -z "$PROJECT_LOCATION" || -z "$RUN_USER" ]]; then
    echo "Usage: sudo bash setup_aws.sh --project <path> --user <username>"
    exit 1
fi

# Resolve ~ for the actual user (not root)
USER_HOME=$(eval echo "~$RUN_USER")
TOKEN_FILE="$USER_HOME/tradingbridge/.token.env"
SENTINEL="$PROJECT_LOCATION/.setup_complete"

echo ""
echo "========================================"
echo "  GOLD Bot — AWS Setup"
echo "========================================"
echo "  Project  : $PROJECT_LOCATION"
echo "  Token    : $TOKEN_FILE  (hardcoded)"
echo "  User     : $RUN_USER"
echo "  Mode     : $([ -f "$SENTINEL" ] && echo 'update' || echo 'first-time')"
echo "========================================"
echo ""

# ── STEP 1: System packages (first-time only) ──────────────────────────────────
if [ ! -f "$SENTINEL" ]; then
    echo "[1/6] Installing system packages (first-time only)..."
    apt-get update -qq
    apt-get install -y python3 python3-pip python3-venv git cron
else
    echo "[1/6] Skipping system packages (already installed)."
fi

# ── STEP 2: Python virtual environment ────────────────────────────────────────
echo "[2/6] Setting up Python virtual environment..."
cd "$PROJECT_LOCATION"

if [ ! -d "venv" ]; then
    echo "  Creating new venv..."
    python3 -m venv venv
fi

source venv/bin/activate
pip install -q --upgrade pip
pip install -q -r requirements.txt
deactivate
echo "  Dependencies installed."

# ── STEP 3: Token file (~/tradingbridge/.token.env) ───────────────────────────
echo "[3/6] Ensuring token directory exists..."
mkdir -p "$USER_HOME/tradingbridge"
chown "$RUN_USER":"$RUN_USER" "$USER_HOME/tradingbridge"
chmod 700 "$USER_HOME/tradingbridge"

if [ ! -f "$TOKEN_FILE" ]; then
    touch "$TOKEN_FILE"
    echo "  *** Token file created at $TOKEN_FILE"
    echo "  *** Populate it on the server with:"
    echo "  ***   echo 'UPSTOX_ACCESS_TOKEN=eyJ0eXAiOi...' > $TOKEN_FILE"
fi
chmod 600 "$TOKEN_FILE"
chown "$RUN_USER":"$RUN_USER" "$TOKEN_FILE"

mkdir -p "$PROJECT_LOCATION/Logs" "$PROJECT_LOCATION/Data"
chown -R "$RUN_USER":"$RUN_USER" "$PROJECT_LOCATION/Logs" "$PROJECT_LOCATION/Data"
echo "  Done."

# ── STEP 4: Runtime config directory ─────────────────────────────────────────
echo "[4/5] Ensuring /etc/gold-bot config directory exists..."
mkdir -p /etc/gold-bot
# Placeholder written here only on first run; deploy.yml overwrites on every push
if [ ! -f /etc/gold-bot/runtime.env ]; then
    cat > /etc/gold-bot/runtime.env <<EOF
TOTAL_LOTS=1
ENABLE_PAPER_TRADING=true
INITIAL_PAPER_CAPITAL=100000.0
EOF
    chmod 644 /etc/gold-bot/runtime.env
    echo "  Created default /etc/gold-bot/runtime.env — will be overwritten by deploy pipeline."
fi

# ── STEP 5: Systemd service ────────────────────────────────────────────────────
echo "[5/6] Installing/updating systemd service...
"
SERVICE_FILE="/etc/systemd/system/gold-4h-breakout.service"

cp "$PROJECT_LOCATION/scripts/gold-4h-breakout.service" "$SERVICE_FILE"
sed -i "s|__USERNAME__|$RUN_USER|g"                  "$SERVICE_FILE"
sed -i "s|__PROJECT_LOCATION__|$PROJECT_LOCATION|g"  "$SERVICE_FILE"

systemctl daemon-reload
systemctl enable gold-4h-breakout.service 2>/dev/null || true
echo "  Service installed and enabled at $SERVICE_FILE"

# ── STEP 5: Cron job — start bot at 09:00 IST (03:30 UTC) Mon-Fri ──────────────
echo "[6/6] Installing daily cron job (09:00 IST / 03:30 UTC, Mon-Fri)..."
CRON_FILE="/etc/cron.d/gold-4h-breakout"
cat > "$CRON_FILE" <<EOF
# Start GOLD bot at 09:00 IST (03:30 UTC) every weekday
30 3 * * 1-5 root /bin/systemctl start gold-4h-breakout.service >> /var/log/gold-4h-breakout-cron.log 2>&1
EOF
chmod 644 "$CRON_FILE"
echo "  Cron installed at $CRON_FILE"

# Fix ownership
chown -R "$RUN_USER":"$RUN_USER" "$PROJECT_LOCATION"
chown root:root "$SERVICE_FILE" "$CRON_FILE"

touch "$SENTINEL"

echo ""
echo "========================================"
echo "  Setup complete!"
echo "========================================"
echo ""
echo "  One-time step — write your Upstox token:"
echo "    echo 'UPSTOX_ACCESS_TOKEN=eyJ0eXAiOi...' > $TOKEN_FILE"
echo ""
echo "  Start manually:"
echo "    sudo systemctl start gold-4h-breakout.service"
echo ""
echo "  Watch logs:"
echo "    tail -f $PROJECT_LOCATION/Logs/GOLD_MARKET.log"
echo ""
