# Camera uploads (FTP + Samba)

On the Debian host, footage lands under `/var/lib/cctv-footage` and FileServer browses it.

## Layout

```text
/var/lib/cctv-footage/
  cam1/
  cam2/
  cam3/
  cam4/
  cam5/
```

Credentials (root only): `/root/fileserver-upload-credentials.txt`

```bash
sudo cat /root/fileserver-upload-credentials.txt
```

## FTP (per camera)

| Setting | Value |
|---|---|
| Host | your server hostname/IP |
| Port | `21` |
| Mode | Passive (`40000–40100`) |
| User | `cam1` … `cam5` |
| Password | see credentials file |
| Remote directory | `/` (user is chrooted to their `camN` folder) |

Plain FTP is enabled because many cameras do not support FTPS. Prefer LAN-only or firewall to trusted camera IPs when you can.

## Samba share `cloud`

| Setting | Value |
|---|---|
| Share name | `cloud` |
| Windows | `\\<host>\cloud` |
| macOS / Linux | `smb://<host>/cloud` |
| User | `cloud` |
| Password | see credentials file |
| Path on server | `/var/lib/cctv-footage` |

Port `445/tcp` must be allowed (UFW rule is added by the host setup).

## Services

```bash
systemctl status vsftpd smbd fileserver
```
