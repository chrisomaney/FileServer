from pathlib import Path

from fastapi.testclient import TestClient

from app.auth import UserStore
from app.config import Settings
from app.main import create_app


def _client(tmp_path: Path) -> TestClient:
    footage = tmp_path / "footage"
    cam = footage / "front"
    cam.mkdir(parents=True)
    (cam / "clip.mp4").write_bytes(b"\x00\x00fake")
    data = tmp_path / "data"
    data.mkdir()
    settings = Settings(
        footage_root=footage,
        data_dir=data,
        session_secret="test-secret-not-for-production-use",
        trust_proxy_headers=False,
    )
    UserStore(settings.users_file).create("admin", "correct-horse-battery-staple")
    app = create_app(settings)
    return TestClient(app)


def test_requires_login(tmp_path: Path) -> None:
    client = _client(tmp_path)
    r = client.get("/", follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["location"] == "/login"


def test_login_and_browse(tmp_path: Path) -> None:
    client = _client(tmp_path)
    page = client.get("/login")
    csrf = page.cookies.get("footage_session")  # session cookie set
    assert page.status_code == 200
    # extract csrf from html
    assert 'name="csrf"' in page.text
    token = page.text.split('name="csrf" value="')[1].split('"')[0]

    bad = client.post(
        "/login",
        data={"username": "admin", "password": "wrong-password-xx", "csrf": token},
        follow_redirects=False,
    )
    assert bad.status_code == 401

    page = client.get("/login")
    token = page.text.split('name="csrf" value="')[1].split('"')[0]
    ok = client.post(
        "/login",
        data={
            "username": "admin",
            "password": "correct-horse-battery-staple",
            "csrf": token,
        },
        follow_redirects=False,
    )
    assert ok.status_code == 303
    assert ok.headers["location"] == "/"

    home = client.get("/")
    assert home.status_code == 200
    assert "front" in home.text

    folder = client.get("/browse/front")
    assert folder.status_code == 200
    assert "clip.mp4" in folder.text

    media = client.get("/media/front/clip.mp4")
    assert media.status_code == 200
    assert media.content == b"\x00\x00fake"


def test_path_traversal_blocked(tmp_path: Path) -> None:
    client = _client(tmp_path)
    page = client.get("/login")
    token = page.text.split('name="csrf" value="')[1].split('"')[0]
    client.post(
        "/login",
        data={
            "username": "admin",
            "password": "correct-horse-battery-staple",
            "csrf": token,
        },
    )
    r = client.get("/media/../.env")
    assert r.status_code in (400, 404)
