#!/usr/bin/env bash
# One-shot bootstrap for the Chat Anonymiser on Amazon Linux 2023.
# Run from an SSM Session Manager session as ec2-user:
#   bash /home/ec2-user/anonymiser/deploy/setup_ec2.sh
set -euo pipefail

APP_DIR=/home/ec2-user/anonymiser
REPO_URL=<your-repo-url>   # ← replace before running

# ── System packages ──────────────────────────────────────────────────────────
sudo dnf update -y
sudo dnf install -y git nginx python3.11 python3.11-pip

# ── Clone repo ───────────────────────────────────────────────────────────────
if [ ! -d "$APP_DIR" ]; then
  git clone "$REPO_URL" "$APP_DIR"
else
  echo "Repo already cloned — skipping clone."
fi

# ── Python venv + dependencies ───────────────────────────────────────────────
python3.11 -m venv "$APP_DIR/.venv"
"$APP_DIR/.venv/bin/pip" install --upgrade pip -q
"$APP_DIR/.venv/bin/pip" install -q -r "$APP_DIR/app/requirements.txt"

# ── Ollama ───────────────────────────────────────────────────────────────────
if ! command -v ollama &>/dev/null; then
  curl -fsSL https://ollama.com/install.sh | sh
fi
sudo systemctl enable --now ollama
sleep 3
ollama pull phi3:3.8b

# ── Systemd service for uvicorn ──────────────────────────────────────────────
sudo cp "$APP_DIR/deploy/anonymiser.service" /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now anonymiser

# ── Nginx ────────────────────────────────────────────────────────────────────
sudo cp "$APP_DIR/deploy/nginx.conf" /etc/nginx/conf.d/anonymiser.conf
sudo rm -f /etc/nginx/conf.d/default.conf
sudo nginx -t
sudo systemctl enable --now nginx

# ── X-Ray daemon ─────────────────────────────────────────────────────────────
sudo dnf install -y aws-xray-daemon
sudo systemctl enable --now aws-xray-daemon

# ── Done ─────────────────────────────────────────────────────────────────────
# Fetch public IP via IMDSv2 (HttpTokens=required)
TOKEN=$(curl -s -X PUT "http://169.254.169.254/latest/api/token" \
  -H "X-aws-ec2-metadata-token-ttl-seconds: 21600")
PUBLIC_IP=$(curl -s -H "X-aws-ec2-metadata-token: $TOKEN" \
  http://169.254.169.254/latest/meta-data/public-ipv4)

echo ""
echo "Deploy complete. App is at http://$PUBLIC_IP"
echo ""
echo "Useful commands:"
echo "  sudo journalctl -u anonymiser -f   # app logs"
echo "  sudo journalctl -u ollama -f       # ollama logs"
echo "  sudo systemctl status anonymiser   # service status"
