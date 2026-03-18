#!/bin/bash
# ─── nunuIRL — One-command VPS deployment ──────────────────────────────────
#
# FIRST-TIME SETUP (run once on a fresh VPS):
#   1. SSH into your VPS
#   2. Install dependencies:
#        sudo apt update && sudo apt install -y docker.io docker-compose-plugin git nginx
#        sudo systemctl enable docker && sudo systemctl start docker
#   3. Clone the repo:
#        git clone <your-repo-url> /opt/nunuirl
#        cd /opt/nunuirl
#   4. Copy and fill in your environment file:
#        cp infra/.env.production.example .env
#        nano .env   ← fill in your API keys and domain
#   5. Set up nginx:
#        sudo cp infra/nginx.conf /etc/nginx/sites-available/nunuirl
#        sudo ln -s /etc/nginx/sites-available/nunuirl /etc/nginx/sites-enabled/
#        sudo rm -f /etc/nginx/sites-enabled/default
#        sudo nginx -t && sudo systemctl reload nginx
#   6. Point your Namecheap domain DNS:
#        A Record: @ → your VPS IP address
#        A Record: www → your VPS IP address
#        (DNS changes take up to 48h but usually <1h)
#   7. Get free SSL certificate:
#        sudo apt install certbot python3-certbot-nginx
#        sudo certbot --nginx -d yourdomain.com -d www.yourdomain.com
#   8. Run this script: bash infra/deploy.sh
#
# SUBSEQUENT DEPLOYS (after first-time setup):
#   git pull && bash infra/deploy.sh
#
# ─────────────────────────────────────────────────────────────────────────────

set -e

COMPOSE_FILE="infra/docker-compose.yml"
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

echo "==> nunuIRL deploy — $(date)"
echo "==> Project dir: $PROJECT_DIR"
cd "$PROJECT_DIR"

# Check .env exists
if [ ! -f ".env" ]; then
    echo "ERROR: .env file not found."
    echo "       Copy infra/.env.production.example to .env and fill in your secrets."
    exit 1
fi

# Pull latest code (skip if running from CI or if you want manual deploys)
if [ "${SKIP_PULL:-0}" != "1" ]; then
    echo "==> Pulling latest code..."
    git pull origin main || echo "   (git pull skipped — not on main or no remote)"
fi

# Build and start all services
echo "==> Building Docker images..."
docker compose -f "$COMPOSE_FILE" build --parallel

echo "==> Starting services (detached)..."
docker compose -f "$COMPOSE_FILE" up -d

# Wait a moment and show status
sleep 3
echo ""
echo "==> Service status:"
docker compose -f "$COMPOSE_FILE" ps

echo ""
echo "==> Done! Your platform should be live at your domain."
echo "    API health check: curl http://localhost:8000/health"
echo "    Web:              http://localhost:3000"
echo ""
echo "    If using nginx, visit: https://yourdomain.com"
