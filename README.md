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

`fileserver-create-user` is installed by `deploy/install.sh`. If you already installed an older copy, pull/update and re-run `sudo ./deploy/install.sh`, or create a user with:

```bash
sudo /opt/FileServer/.venv/bin/python /opt/FileServer/scripts/create_user.py
```

Then point nginx at the app (`deploy/nginx.conf`), issue a Let’s Encrypt cert, and put camera recordings under `/var/lib/cctv-footage` (or change `FOOTAGE_ROOT`).

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

## License

Private / all rights reserved unless you add one.
