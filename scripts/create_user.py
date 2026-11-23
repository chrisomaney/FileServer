#!/usr/bin/env python3
"""Create a FileServer login (argon2 hash stored in data/users.json)."""

from __future__ import annotations

import argparse
import getpass
import sys
from pathlib import Path

# Allow `python -m scripts.create_user` from repo root.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.auth import UserStore
from app.config import get_settings


def main() -> int:
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
