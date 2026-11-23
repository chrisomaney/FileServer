from __future__ import annotations

import mimetypes
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


VIDEO_EXTS = {".mp4", ".mkv", ".webm", ".mov", ".avi", ".m4v"}
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}


@dataclass(frozen=True)
class Entry:
    name: str
    rel_path: str
    is_dir: bool
    size: int
    mtime: float
    kind: str  # dir | video | image | file

    @property
    def size_label(self) -> str:
        if self.is_dir:
            return "—"
        return format_bytes(self.size)

    @property
    def mtime_label(self) -> str:
        return datetime.fromtimestamp(self.mtime, tz=timezone.utc).strftime(
            "%Y-%m-%d %H:%M UTC"
        )


def format_bytes(num: int) -> str:
    value = float(num)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if value < 1024 or unit == "TB":
            if unit == "B":
                return f"{int(value)} {unit}"
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{num} B"


def safe_resolve(root: Path, rel: str) -> Path:
    """Resolve rel under root; raise ValueError on traversal."""
    root = root.resolve()
    # Normalize separators and strip leading slashes.
    cleaned = rel.replace("\\", "/").lstrip("/")
    if ".." in Path(cleaned).parts:
        raise ValueError("invalid path")
    target = (root / cleaned).resolve()
    try:
        target.relative_to(root)
    except ValueError as exc:
        raise ValueError("path escapes footage root") from exc
    return target


def classify(path: Path) -> str:
    if path.is_dir():
        return "dir"
    ext = path.suffix.lower()
    if ext in VIDEO_EXTS:
        return "video"
    if ext in IMAGE_EXTS:
        return "image"
    return "file"


def list_directory(root: Path, rel: str = "", query: str = "") -> tuple[Path, list[Entry]]:
    directory = safe_resolve(root, rel)
    if not directory.exists():
        raise FileNotFoundError(rel)
    if not directory.is_dir():
        raise NotADirectoryError(rel)

    q = query.strip().lower()
    entries: list[Entry] = []
    with os.scandir(directory) as it:
        for item in it:
            name = item.name
            if name.startswith("."):
                continue
            if q and q not in name.lower():
                continue
            try:
                stat = item.stat(follow_symlinks=False)
            except OSError:
                continue
            # Never follow symlinks out of the jail.
            if item.is_symlink():
                continue
            is_dir = item.is_dir(follow_symlinks=False)
            child_rel = str(Path(rel) / name) if rel else name
            kind = "dir" if is_dir else classify(Path(name))
            entries.append(
                Entry(
                    name=name,
                    rel_path=child_rel.replace("\\", "/"),
                    is_dir=is_dir,
                    size=0 if is_dir else int(stat.st_size),
                    mtime=float(stat.st_mtime),
                    kind=kind,
                )
            )

    entries.sort(key=lambda e: (not e.is_dir, e.name.lower()))
    return directory, entries


def parent_rel(rel: str) -> str | None:
    if not rel:
        return None
    parent = str(Path(rel).parent)
    if parent == ".":
        return ""
    return parent.replace("\\", "/")


def guess_media_type(path: Path) -> str:
    guessed, _ = mimetypes.guess_type(str(path))
    return guessed or "application/octet-stream"
