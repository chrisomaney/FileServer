# FileServer

Simple, secure web UI for browsing and streaming CCTV footage on a **Debian 12** server.

- Login required (argon2 password hashes)
- Path jail: only files under `FOOTAGE_ROOT` are visible
- Symlinks are ignored (no escape via links)
- CSRF-protected login/logout forms
- Failed-login rate limiting
- Security headers + Content-Security-Policy
- Range-friendly media responses for video seeking
- systemd unit + nginx TLS reverse-proxy example

## Quick start (dev)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

export SESSION_SECRET="$(openssl rand -hex 32)"
export FOOTAGE_ROOT="$(pwd)/demo-footage"
export DATA_DIR="$(pwd)/data"
mkdir -p "$FOOTAGE_ROOT/camera1" "$DATA_DIR"
# drop some .mp4/.jpg files into demo-footage/

python -m scripts.create_user admin
./scripts/run.sh
# open http://127.0.0.1:8080
```

## Debian 12 install

`git` is not installed by default on a minimal Debian image. Install it first:

```bash
sudo apt-get update
sudo apt-get install -y git
git clone https://github.com/chrisomaney/FileServer.git
cd FileServer
sudo ./deploy/install.sh
sudo fileserver-create-user
```

No git? Download a zip instead:

```bash
sudo apt-get update
sudo apt-get install -y curl unzip
curl -L -o FileServer.zip https://github.com/chrisomaney/FileServer/archive/refs/heads/main.zip
unzip FileServer.zip
cd FileServer-main
sudo ./deploy/install.sh
sudo fileserver-create-user
```

`fileserver-create-user` is installed by `deploy/install.sh`. If you already installed an older copy:

```bash
cd ~/FileServer   # or your clone path
git pull
sudo ./deploy/install.sh
sudo fileserver-create-user
```

Then point a reverse proxy at the app (`deploy/nginx.conf`, or Apache on this host), issue a Let’s Encrypt cert, and put camera recordings under `/var/lib/cctv-footage` (or change `FOOTAGE_ROOT`).

### Camera uploads (FTP + Samba `cloud`)

Cameras do not upload into the web UI. They write into `/var/lib/cctv-footage` via **FTP** (`cam1`…`cam5`) and/or the Samba share named **`cloud`**.

See `deploy/uploads.md`. On a configured host, credentials are in:

```bash
sudo cat /root/fileserver-upload-credentials.txt
```

## CCTV FTP uploads (cameras → folders)

IP cameras that upload over FTP can write into per-camera folders under `FOOTAGE_ROOT`. On the Debian host:

```bash
sudo ./deploy/setup-cctv-ftp.sh
```

That installs **vsftpd**, creates local users `cam1`…`cam5` chrooted to `/var/lib/cctv-footage/camN`, opens UFW for `21/tcp` and passive `40000-40100/tcp`, and writes credentials to **`/root/fileserver-ftp-credentials.txt`** (mode `600`, root only).

| Camera setting | Value |
|---|---|
| Host | server hostname or IP (e.g. `m4484.contaboserver.net`) |
| Port | `21` |
| Username | `cam1` … `cam5` |
| Password | from `/root/fileserver-ftp-credentials.txt` on the server |
| Remote path | `/` or blank (user is already chrooted to their folder) |
| Mode | Passive FTP |

**Security:** many cameras only speak plain FTP (passwords and footage in cleartext). Users are chrooted and UFW-limited to the FTP ports, but prefer LAN/VPN or FTPS when the cameras support it. Do not paste credentials into chat, tickets, or git.

## Config

See `.env.example`. Important keys:

| Variable | Purpose |
|---|---|
| `SESSION_SECRET` | Cookie signing secret (required in production) |
| `FOOTAGE_ROOT` | Absolute path to footage tree |
| `DATA_DIR` | Stores `users.json` |
| `TRUST_PROXY_HEADERS` | Set `true` behind nginx |

## Security notes

- Keep the app bound to `127.0.0.1` and terminate TLS at nginx.
- Use a long unique `SESSION_SECRET`.
- Prefer strong unique passwords (12+ characters enforced).
- Do not expose the app directly on the public internet without TLS + firewall.
- Footage directory should be readable by the `fileserver` user; write access is not required for browsing.
- Camera FTP (if enabled) uses chrooted `camN` accounts; keep passwords only in `/root/fileserver-ftp-credentials.txt`.

## License

Private / all rights reserved unless you add one.
