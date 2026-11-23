from pathlib import Path

import pytest

from app.files import list_directory, safe_resolve


def test_safe_resolve_blocks_traversal(tmp_path: Path) -> None:
    root = tmp_path / "footage"
    root.mkdir()
    with pytest.raises(ValueError):
        safe_resolve(root, "../etc/passwd")
    with pytest.raises(ValueError):
        safe_resolve(root, "cam/../../etc/passwd")


def test_safe_resolve_inside(tmp_path: Path) -> None:
    root = tmp_path / "footage"
    cam = root / "cam1"
    cam.mkdir(parents=True)
    (cam / "clip.mp4").write_bytes(b"demo")
    resolved = safe_resolve(root, "cam1/clip.mp4")
    assert resolved == (cam / "clip.mp4").resolve()


def test_list_skips_symlinks_and_dotfiles(tmp_path: Path) -> None:
    root = tmp_path / "footage"
    root.mkdir()
    (root / "visible.mp4").write_bytes(b"x")
    (root / ".hidden").write_bytes(b"x")
    outside = tmp_path / "outside.mp4"
    outside.write_bytes(b"y")
    (root / "escape").symlink_to(outside)

    _, entries = list_directory(root, "")
    names = {e.name for e in entries}
    assert names == {"visible.mp4"}
