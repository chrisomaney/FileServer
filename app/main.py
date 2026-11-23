from __future__ import annotations

import secrets
from pathlib import Path
from typing import Annotated, Any
from urllib.parse import quote

from fastapi import Depends, FastAPI, Form, HTTPException, Request, Response, status
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from app import __version__
from app.auth import LoginRateLimiter, UserStore, new_csrf_token
from app.config import Settings, get_settings
from app.files import (
    IMAGE_EXTS,
    VIDEO_EXTS,
    classify,
    format_bytes,
    guess_media_type,
    list_directory,
    parent_rel,
    safe_resolve,
)

BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
templates.env.globals["app_version"] = __version__


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    # Footage root is owned by the NVR/cameras; do not create it at import time.

    users = UserStore(settings.users_file)
    limiter = LoginRateLimiter(settings.login_max_attempts, settings.login_lockout_seconds)

    app = FastAPI(title=settings.app_name, docs_url=None, redoc_url=None, openapi_url=None)
    app.state.settings = settings
    app.state.users = users
    app.state.limiter = limiter

    # Secure session cookies. HTTPS is expected behind nginx in production.
    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.session_secret,
        session_cookie="footage_session",
        max_age=settings.session_hours * 3600,
        same_site="lax",
        https_only=False,  # nginx terminates TLS; set True if serving HTTPS directly
    )

    app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

    @app.middleware("http")
    async def security_headers(request: Request, call_next):  # type: ignore[no-untyped-def]
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response.headers["Cache-Control"] = "no-store"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "img-src 'self' blob: data:; "
            "media-src 'self' blob:; "
            "style-src 'self' 'unsafe-inline'; "
            "script-src 'self'; "
            "frame-ancestors 'none'; "
            "base-uri 'self'; "
            "form-action 'self'"
        )
        return response

    def client_key(request: Request) -> str:
        if settings.trust_proxy_headers:
            forwarded = request.headers.get("x-forwarded-for", "")
            if forwarded:
                return forwarded.split(",")[0].strip()
        return request.client.host if request.client else "unknown"

    def current_user(request: Request) -> str | None:
        username = request.session.get("user")
        if isinstance(username, str) and users.get(username):
            return username
        return None

    def require_user(request: Request) -> str:
        user = current_user(request)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_303_SEE_OTHER,
                headers={"Location": "/login"},
            )
        return user

    def ensure_csrf(request: Request, token: str) -> None:
        expected = request.session.get("csrf")
        if not expected or not token or not secrets.compare_digest(str(expected), token):
            raise HTTPException(status_code=400, detail="Invalid CSRF token")

    def breadcrumbs(rel: str) -> list[dict[str, str]]:
        crumbs = [{"label": "Footage", "href": "/"}]
        if not rel:
            return crumbs
        parts = Path(rel).parts
        acc: list[str] = []
        for part in parts:
            acc.append(part)
            crumbs.append({"label": part, "href": "/browse/" + quote("/".join(acc))})
        return crumbs

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok", "version": __version__}

    @app.get("/login", response_class=HTMLResponse)
    def login_page(request: Request) -> Any:
        if current_user(request):
            return RedirectResponse("/", status_code=303)
        if not request.session.get("csrf"):
            request.session["csrf"] = new_csrf_token()
        return templates.TemplateResponse(
            request,
            "login.html",
            {
                "app_name": settings.app_name,
                "csrf": request.session["csrf"],
                "error": None,
                "has_users": bool(users.list_usernames()),
            },
        )

    @app.post("/login")
    def login_submit(
        request: Request,
        username: Annotated[str, Form()],
        password: Annotated[str, Form()],
        csrf: Annotated[str, Form()],
    ) -> Any:
        ensure_csrf(request, csrf)
        key = client_key(request)
        if limiter.is_locked(key):
            request.session["csrf"] = new_csrf_token()
            return templates.TemplateResponse(
                request,
                "login.html",
                {
                    "app_name": settings.app_name,
                    "csrf": request.session["csrf"],
                    "error": "Too many failed attempts. Try again later.",
                    "has_users": bool(users.list_usernames()),
                },
                status_code=429,
            )

        if users.verify(username.strip(), password):
            limiter.clear(key)
            request.session.clear()
            request.session["user"] = username.strip()
            request.session["csrf"] = new_csrf_token()
            return RedirectResponse("/", status_code=303)

        limiter.record_failure(key)
        request.session["csrf"] = new_csrf_token()
        return templates.TemplateResponse(
            request,
            "login.html",
            {
                "app_name": settings.app_name,
                "csrf": request.session["csrf"],
                "error": "Invalid username or password.",
                "has_users": bool(users.list_usernames()),
            },
            status_code=401,
        )

    @app.post("/logout")
    def logout(
        request: Request,
        csrf: Annotated[str, Form()],
    ) -> RedirectResponse:
        ensure_csrf(request, csrf)
        request.session.clear()
        return RedirectResponse("/login", status_code=303)

    def ensure_footage_root() -> None:
        if not settings.footage_root.exists() or not settings.footage_root.is_dir():
            raise HTTPException(
                status_code=503,
                detail=f"Footage root not available: {settings.footage_root}",
            )

    @app.get("/", response_class=HTMLResponse)
    def home(request: Request, q: str = "") -> Any:
        user = current_user(request)
        if not user:
            return RedirectResponse("/login", status_code=303)
        return browse(request, path="", q=q, user=user)

    @app.get("/browse/{path:path}", response_class=HTMLResponse)
    def browse(
        request: Request,
        path: str = "",
        q: str = "",
        user: str | None = None,
    ) -> Any:
        user = user or require_user(request)
        ensure_footage_root()
        try:
            directory, entries = list_directory(settings.footage_root, path, q)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid path") from None
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail="Not found") from None
        except NotADirectoryError:
            # If it's a file, open the viewer.
            return RedirectResponse(f"/view/{quote(path)}", status_code=303)

        rel = path.strip("/")
        return templates.TemplateResponse(
            request,
            "browse.html",
            {
                "app_name": settings.app_name,
                "user": user,
                "csrf": request.session.get("csrf") or new_csrf_token(),
                "entries": entries,
                "rel": rel,
                "query": q,
                "breadcrumbs": breadcrumbs(rel),
                "parent": parent_rel(rel),
                "root_label": str(settings.footage_root),
                "count": len(entries),
            },
        )

    @app.get("/view/{path:path}", response_class=HTMLResponse)
    def view_file(request: Request, path: str) -> Any:
        user = require_user(request)
        ensure_footage_root()
        try:
            target = safe_resolve(settings.footage_root, path)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid path") from None
        if not target.exists() or not target.is_file() or target.is_symlink():
            raise HTTPException(status_code=404, detail="Not found")

        kind = classify(target)
        rel = path.strip("/")
        return templates.TemplateResponse(
            request,
            "view.html",
            {
                "app_name": settings.app_name,
                "user": user,
                "csrf": request.session.get("csrf") or new_csrf_token(),
                "name": target.name,
                "rel": rel,
                "kind": kind,
                "size_label": format_bytes(target.stat().st_size),
                "media_url": f"/media/{quote(rel)}",
                "download_url": f"/download/{quote(rel)}",
                "breadcrumbs": breadcrumbs(rel),
                "parent": parent_rel(rel),
                "is_video": target.suffix.lower() in VIDEO_EXTS,
                "is_image": target.suffix.lower() in IMAGE_EXTS,
            },
        )

    def _authenticated_file(request: Request, path: str, download: bool) -> FileResponse:
        require_user(request)
        ensure_footage_root()
        try:
            target = safe_resolve(settings.footage_root, path)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid path") from None
        if not target.exists() or not target.is_file() or target.is_symlink():
            raise HTTPException(status_code=404, detail="Not found")

        media_type = guess_media_type(target)
        headers = {"Accept-Ranges": "bytes"}
        if download:
            headers["Content-Disposition"] = f'attachment; filename="{target.name}"'
        return FileResponse(
            path=target,
            media_type=media_type,
            filename=target.name if download else None,
            headers=headers,
        )

    @app.get("/media/{path:path}")
    def media(request: Request, path: str) -> FileResponse:
        return _authenticated_file(request, path, download=False)

    @app.get("/download/{path:path}")
    def download(request: Request, path: str) -> FileResponse:
        return _authenticated_file(request, path, download=True)

    return app


app = create_app()
