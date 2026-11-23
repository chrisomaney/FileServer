#!/usr/bin/env python3
"""Create a FileServer login (argon2 hash stored in users.json)."""

from __future__ import annotations

import argparse
import getpass
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _load_env_file(path: Path) -> None:
    """Load KEY=VALUE lines into the process env if not already set."""
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip("'").strip('"')
        if key and key not in os.environ:
            os.environ[key] = value


def main() -> int:
    # Prefer the installed Debian env so users land where the service looks.
    _load_env_file(Path("/etc/fileserver.env"))
    _load_env_file(ROOT / ".env")

    # Import after env load so Settings picks up DATA_DIR etc.
    from app.auth import UserStore
    from app.config import get_settings

    get_settings.cache_clear()

    parser = argparse.ArgumentParser(description="Create a FileServer user")
    parser.add_argument("username", nargs="?", help="Login username")
    parser.add_argument(
        "--password",
        help="Password (prefer omit and type interactively)",
    )
    args = parser.parse_args()

    username = args.username or input("Username: ").strip()
    password = args.password
    if not password:
        password = getpass.getpass("Password (min 12 chars): ")
        confirm = getpass.getpass("Confirm password: ")
        if password != confirm:
            print("Passwords do not match.", file=sys.stderr)
            return 1

    settings = get_settings()
    store = UserStore(settings.users_file)
    try:
        store.create(username, password)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(f"Created user {username!r} in {settings.users_file}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
