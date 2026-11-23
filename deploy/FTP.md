# CCTV FTP (vsftpd) for FileServer

## Purpose

Five cameras upload footage into separate folders that the FileServer web UI browses:

```
/var/lib/cctv-footage/
  cam1/   ← FTP user cam1 (chroot)
  cam2/   ← FTP user cam2
  cam3/
  cam4/
  cam5/
```

## Install / reconfigure

```bash
sudo ./deploy/setup-cctv-ftp.sh
```

Credentials are written only to `/root/fileserver-ftp-credentials.txt` (root, mode 600).

## Camera configuration

- **Host:** public hostname or IP of the Debian host
- **Port:** 21
- **User:** `cam1` … `cam5` (one per camera)
- **Password:** from the credentials file on the server
- **Path:** `/` or empty (chroot home is already the camera folder)
- **Transfer mode:** passive (PASV ports 40000–40100)
- **Encryption:** plain FTP (typical for IP cams)

## Firewall

UFW allows:

- `21/tcp` — FTP control
- `40000:40100/tcp` — passive data

Optionally restrict these rules to camera LAN/VPN source IPs.

## Permissions

- Folders are `camN:fileserver` with setgid (`2775`) so uploads inherit the `fileserver` group.
- `local_umask=002` so the web app can read new files.
- Parent `/var/lib/cctv-footage` stays group-readable by `fileserver`.

## Risks and follow-ups

- **Plain FTP** exposes credentials on the wire. Prefer FTPS (`ssl_enable=YES` + camera FTPS support) or keep cameras on a private network/VPN.
- Set `pasv_address` to the address cameras actually reach (public IP vs LAN). Contabo VPS usually needs the public IP for remote PASV.
- Consider locking UFW FTP rules to known camera IPs.
- Samba/`cloud` share (if present on the host) is separate from camera FTP; manage with `smbpasswd` if used.
