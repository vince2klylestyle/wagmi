#!/bin/bash
# ============================================================
# nunuIRL Deployment Script - Hetzner VPS Setup
# ============================================================
# Run this on a fresh Hetzner CX23 (Ubuntu 22.04+)
#
# STEP 1: Create a Hetzner Cloud account at https://hetzner.cloud
# STEP 2: Create a CX23 server (2 vCPU, 4GB RAM, ~$4.50/month)
#         - Location: Falkenstein or Nuremberg (Germany)
#         - OS: Ubuntu 22.04
#         - Add your SSH key
# STEP 3: SSH into the server: ssh root@<ip>
# STEP 4: Run this script:
#         curl -sSL <raw-github-url>/deploy.sh | bash
#   OR:   git clone <repo> && cd <repo> && bash deploy.sh
# ============================================================

set -e

echo "============================================"
echo "nunuIRL Trading Bot - VPS Setup"
echo "============================================"

# ── System packages ──────────────────────────────────────────
echo "[1/6] Installing system packages..."
apt-get update -qq
apt-get install -y -qq python3 python3-pip python3-venv git tmux htop

# ── Create bot user (don't run as root) ──────────────────────
echo "[2/6] Creating bot user..."
if ! id -u nunuirl &>/dev/null; then
    useradd -m -s /bin/bash nunuirl
fi

# ── Clone or update repo ─────────────────────────────────────
echo "[3/6] Setting up code..."
BOT_DIR="/home/nunuirl/bot"
if [ -d "$BOT_DIR" ]; then
    echo "  Updating existing installation..."
    cd "$BOT_DIR"
    git pull
else
    echo "  Fresh clone..."
    # If running from the repo, copy; otherwise clone
    if [ -d "bot" ]; then
        cp -r . /home/nunuirl/bot
    else
        echo "  Please clone the repo to /home/nunuirl/bot manually"
        echo "  git clone <your-repo-url> /home/nunuirl/bot"
        exit 1
    fi
fi

cd "$BOT_DIR/bot"

# ── Python environment ───────────────────────────────────────
echo "[4/6] Setting up Python environment..."
python3 -m venv /home/nunuirl/venv
source /home/nunuirl/venv/bin/activate
pip install --quiet --upgrade pip
pip install --quiet -r "$BOT_DIR/bot/requirements.txt"

# Optional: matplotlib for plots (adds ~50MB)
pip install --quiet matplotlib 2>/dev/null || echo "  (matplotlib skipped - install later with: pip install matplotlib)"

# ── Configuration ────────────────────────────────────────────
echo "[5/6] Configuration..."
if [ ! -f "$BOT_DIR/bot/.env" ]; then
    cp "$BOT_DIR/bot/.env.production" "$BOT_DIR/bot/.env"
    echo ""
    echo "  ============================================"
    echo "  IMPORTANT: Edit your .env file with secrets:"
    echo "  nano $BOT_DIR/bot/.env"
    echo ""
    echo "  You MUST set:"
    echo "    TELEGRAM_TOKEN=<from @BotFather>"
    echo "    TELEGRAM_CHAT_ID=<from @userinfobot>"
    echo "    TELEGRAM_ALLOWED_USER_ID=<from @RawDataBot>"
    echo "    ANTHROPIC_API_KEY=<from console.anthropic.com>"
    echo "    STARTING_EQUITY=<your actual deposit>"
    echo "  ============================================"
    echo ""
else
    echo "  .env already exists, not overwriting"
fi

# ── Create data directories ──────────────────────────────────
mkdir -p "$BOT_DIR/bot/data/llm"
mkdir -p "$BOT_DIR/bot/data/logs"
mkdir -p "$BOT_DIR/bot/data/analysis"
mkdir -p "$BOT_DIR/bot/ml_data"
mkdir -p "$BOT_DIR/bot/paper_trades"
mkdir -p "$BOT_DIR/bot/logs"

# ── Systemd service ──────────────────────────────────────────
echo "[6/6] Creating systemd service..."
cat > /etc/systemd/system/nunuirl.service << 'UNIT'
[Unit]
Description=nunuIRL Trading Bot
After=network.target
Wants=network-online.target

[Service]
Type=simple
User=nunuirl
WorkingDirectory=/home/nunuirl/bot/bot
Environment=PATH=/home/nunuirl/venv/bin:/usr/bin:/bin
ExecStart=/home/nunuirl/venv/bin/python run.py paper
Restart=always
RestartSec=30
StandardOutput=append:/home/nunuirl/bot/bot/logs/stdout.log
StandardError=append:/home/nunuirl/bot/bot/logs/stderr.log

# Safety: restart limit (max 5 restarts in 5 minutes)
StartLimitBurst=5
StartLimitIntervalSec=300

[Install]
WantedBy=multi-user.target
UNIT

systemctl daemon-reload
systemctl enable nunuirl

# Fix ownership
chown -R nunuirl:nunuirl /home/nunuirl/

echo ""
echo "============================================"
echo "Setup complete!"
echo "============================================"
echo ""
echo "Next steps:"
echo "  1. Edit config:  nano $BOT_DIR/bot/.env"
echo "  2. Start bot:    systemctl start nunuirl"
echo "  3. Watch logs:   journalctl -u nunuirl -f"
echo "  4. Bot status:   systemctl status nunuirl"
echo "  5. Stop bot:     systemctl stop nunuirl"
echo ""
echo "Paper trading:     ExecStart uses 'run.py paper'"
echo "Go live:           Edit .env -> ENVIRONMENT=production"
echo "                   Edit service -> 'run.py paper' (yes, same)"
echo "                   The ENVIRONMENT var controls behavior."
echo ""
echo "Quick commands:"
echo "  tmux new -s bot   # persistent terminal session"
echo "  htop              # monitor CPU/RAM"
echo "  tail -f $BOT_DIR/bot/logs/bot_*.log  # live logs"
echo ""
echo "LLM analytics (run after sessions):"
echo "  cd $BOT_DIR/bot && python -m llm.analyze"
echo "  cd $BOT_DIR/bot && python -m llm.analyze --focus regimes"
echo "============================================"
