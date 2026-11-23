#!/usr/bin/env bash
# Install and configure vsftpd for CCTV camera uploads into FileServer footage folders.
# Run as root on the Debian host. Creates cam1..cam5 users, chrooted to
# /var/lib/cctv-footage/camN. Credentials written ONLY to
# /root/fileserver-ftp-credentials.txt (mode 600).
set -euo pipefail

if [[ "${EUID}" -ne 0 ]]; then
  echo "Run as root: sudo ./deploy/setup-cctv-ftp.sh" >&2
  exit 1
fi

FOOTAGE_ROOT="${FOOTAGE_ROOT:-/var/lib/cctv-footage}"
CRED_FILE="${CRED_FILE:-/root/fileserver-ftp-credentials.txt}"
USERLIST=/etc/vsftpd.userlist
PASV_MIN=40000
PASV_MAX=40100
CAM_COUNT=5

# Plain FTP is common for IP cameras; keep users chrooted. Prefer FTPS when cameras support it.
# Risk: credentials and footage traverse the network unencrypted on port 21 / PASV range.

apt-get update
apt-get install -y vsftpd openssl

id fileserver &>/dev/null || useradd --system --home /var/lib/fileserver --shell /usr/sbin/nologin fileserver

mkdir -p "$FOOTAGE_ROOT"
chown root:fileserver "$FOOTAGE_ROOT"
chmod 750 "$FOOTAGE_ROOT"

# Public address for PASV (Contabo / remote cameras). Override with PASV_ADDRESS=...
if [[ -z "${PASV_ADDRESS:-}" ]]; then
  PASV_ADDRESS="$(curl -4 -fsS --max-time 5 ifconfig.me 2>/dev/null || true)"
fi
if [[ -z "${PASV_ADDRESS}" ]]; then
  PASV_ADDRESS="$(hostname -I | awk '{print $1}')"
fi

# Backup existing config once
if [[ -f /etc/vsftpd.conf && ! -f /etc/vsftpd.conf.fileserver.bak ]]; then
  cp -a /etc/vsftpd.conf /etc/vsftpd.conf.fileserver.bak
fi

cat >/etc/vsftpd.conf <<EOF
# FileServer CCTV FTP — managed by deploy/setup-cctv-ftp.sh
listen=YES
listen_ipv6=NO
anonymous_enable=NO
local_enable=YES
write_enable=YES
local_umask=002
dirmessage_enable=YES
use_localtime=YES
xferlog_enable=YES
xferlog_file=/var/log/vsftpd.log
connect_from_port_20=YES
chroot_local_user=YES
allow_writeable_chroot=YES
secure_chroot_dir=/var/run/vsftpd/empty
pam_service_name=vsftpd
userlist_enable=YES
userlist_file=${USERLIST}
userlist_deny=NO
pasv_enable=YES
pasv_min_port=${PASV_MIN}
pasv_max_port=${PASV_MAX}
pasv_address=${PASV_ADDRESS}
# Plain FTP for typical IP cameras (credentials unencrypted). Restrict source IPs in UFW when possible.
ssl_enable=NO
idle_session_timeout=600
data_connection_timeout=120
max_clients=20
max_per_ip=5
EOF

: >"$USERLIST"
chmod 644 "$USERLIST"

umask 077
{
  echo "# FileServer CCTV FTP credentials — root only. Generated $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "# Host: $(hostname -f 2>/dev/null || hostname)"
  echo "# FTP: plain FTP port 21, passive ${PASV_MIN}-${PASV_MAX}, pasv_address=${PASV_ADDRESS}"
  echo "# Folder layout (server path): ${FOOTAGE_ROOT}/camN  (chroot = that folder; camera upload path / or empty)"
  echo "# WARNING: plain FTP sends passwords in cleartext. Prefer LAN/VPN or FTPS when cameras support it."
  echo
} >"$CRED_FILE"
chmod 600 "$CRED_FILE"

for i in $(seq 1 "$CAM_COUNT"); do
  user="cam${i}"
  home="${FOOTAGE_ROOT}/${user}"
  mkdir -p "$home"

  if ! id "$user" &>/dev/null; then
    useradd --system --home-dir "$home" --shell /usr/sbin/nologin --gid fileserver "$user"
  else
    usermod --home "$home" --shell /usr/sbin/nologin --gid fileserver "$user"
  fi

  # setgid so new uploads inherit fileserver group for the web UI
  chown "${user}:fileserver" "$home"
  chmod 2775 "$home"

  pass="$(openssl rand -base64 24 | tr -d '/+=' | head -c 24)"
  echo "${user}:${pass}" | chpasswd
  echo "$user" >>"$USERLIST"
  {
    echo "user=${user}"
    echo "password=${pass}"
    echo "home=${home}"
    echo "ftp_path=/"
    echo
  } >>"$CRED_FILE"
done

chmod 600 "$CRED_FILE"
chown root:root "$CRED_FILE"

if command -v ufw >/dev/null 2>&1; then
  ufw allow 21/tcp comment 'vsftpd control' || true
  ufw allow "${PASV_MIN}:${PASV_MAX}/tcp" comment 'vsftpd passive' || true
fi

mkdir -p /var/run/vsftpd/empty
chmod 755 /var/run/vsftpd/empty
systemctl enable vsftpd
systemctl restart vsftpd

echo
echo "vsftpd configured for cam1..cam${CAM_COUNT}."
echo "Credentials: ${CRED_FILE} (root only — do not commit or paste into chat)."
echo "Footage root: ${FOOTAGE_ROOT}/camN"
echo "UFW: allow 21/tcp and ${PASV_MIN}:${PASV_MAX}/tcp"
echo "PASV address: ${PASV_ADDRESS}"
echo "Camera settings: host=<server>, port=21, user=camN, path=/ (or blank), mode=passive FTP"
