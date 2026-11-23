#!/usr/bin/env bash
# Install FileServer on Debian 12. Run as root from the cloned repo.
set -euo pipefail

if [[ "${EUID}" -ne 0 ]]; then
  echo "Run as root: sudo ./deploy/install.sh" >&2
  exit 1
fi

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
APP_DIR=/opt/FileServer
DATA_DIR=/var/lib/fileserver
FOOTAGE_DIR=/var/lib/cctv-footage
ENV_FILE=/etc/fileserver.env

apt-get update
apt-get install -y python3 python3-venv python3-pip nginx

id fileserver &>/dev/null || useradd --system --home "$DATA_DIR" --shell /usr/sbin/nologin fileserver

mkdir -p "$APP_DIR" "$DATA_DIR" "$FOOTAGE_DIR"
rsync -a --delete \
  --exclude '.git' \
  --exclude '.venv' \
  --exclude 'data' \
  --exclude '__pycache__' \
  "$REPO_ROOT"/ "$APP_DIR"/

python3 -m venv "$APP_DIR/.venv"
"$APP_DIR/.venv/bin/pip" install --upgrade pip
"$APP_DIR/.venv/bin/pip" install -r "$APP_DIR/requirements.txt"

if [[ ! -f "$ENV_FILE" ]]; then
  SECRET="$(openssl rand -hex 32)"
  cat > "$ENV_FILE" <<EOF
SESSION_SECRET=${SECRET}
FOOTAGE_ROOT=${FOOTAGE_DIR}
DATA_DIR=${DATA_DIR}
APP_NAME=FileServer
HOST=127.0.0.1
PORT=8080
TRUST_PROXY_HEADERS=true
EOF
  chmod 600 "$ENV_FILE"
fi

chown -R fileserver:fileserver "$APP_DIR" "$DATA_DIR"
# Footage is usually written by NVR/cameras — keep readable by the app user.
chown root:fileserver "$FOOTAGE_DIR"
chmod 750 "$FOOTAGE_DIR"

install -m 644 "$APP_DIR/deploy/fileserver.service" /etc/systemd/system/fileserver.service
systemctl daemon-reload
systemctl enable --now fileserver.service

echo
echo "FileServer installed."
echo "1. Put footage under ${FOOTAGE_DIR} (or edit FOOTAGE_ROOT in ${ENV_FILE})"
echo "2. Create a login:"
echo "   sudo -u fileserver ${APP_DIR}/.venv/bin/python -m scripts.create_user"
echo "3. Copy deploy/nginx.conf, set your domain, enable site, get a cert:"
echo "   certbot --nginx -d footage.example.com"
echo "4. Check: systemctl status fileserver && curl -s http://127.0.0.1:8080/healthz"
