from __future__ import annotations

import json
import secrets
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")


@dataclass(frozen=True)
class User:
    username: str
    password_hash: str


class UserStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self._write({"users": []})

    def _read(self) -> dict[str, Any]:
        with self.path.open("r", encoding="utf-8") as fh:
            return json.load(fh)

    def _write(self, payload: dict[str, Any]) -> None:
        tmp = self.path.with_suffix(".tmp")
        with tmp.open("w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2)
            fh.write("\n")
        tmp.replace(self.path)
        try:
            self.path.chmod(0o600)
        except OSError:
            pass

    def list_usernames(self) -> list[str]:
        return [u["username"] for u in self._read().get("users", [])]

    def get(self, username: str) -> User | None:
        for row in self._read().get("users", []):
            if row.get("username") == username:
                return User(username=username, password_hash=row["password_hash"])
        return None

    def create(self, username: str, password: str) -> None:
        username = username.strip()
        if not username or len(username) > 64:
            raise ValueError("username must be 1–64 characters")
        if len(password) < 12:
            raise ValueError("password must be at least 12 characters")
        if self.get(username):
            raise ValueError(f"user already exists: {username}")
        data = self._read()
        data.setdefault("users", []).append(
            {
                "username": username,
                "password_hash": pwd_context.hash(password),
            }
        )
        self._write(data)

    def verify(self, username: str, password: str) -> bool:
        user = self.get(username)
        if user is None:
            # Constant-time-ish dummy verify to reduce user enumeration timing.
            pwd_context.verify(password, pwd_context.hash("dummy-password-check"))
            return False
        return pwd_context.verify(password, user.password_hash)


class LoginRateLimiter:
    """In-memory failed-login tracker keyed by client IP."""

    def __init__(self, max_attempts: int, lockout_seconds: int) -> None:
        self.max_attempts = max_attempts
        self.lockout_seconds = lockout_seconds
        self._failures: dict[str, list[float]] = {}

    def is_locked(self, key: str) -> bool:
        now = time.monotonic()
        window = now - self.lockout_seconds
        stamps = [t for t in self._failures.get(key, []) if t >= window]
        self._failures[key] = stamps
        return len(stamps) >= self.max_attempts

    def record_failure(self, key: str) -> None:
        self._failures.setdefault(key, []).append(time.monotonic())

    def clear(self, key: str) -> None:
        self._failures.pop(key, None)


def new_csrf_token() -> str:
    return secrets.token_urlsafe(32)
