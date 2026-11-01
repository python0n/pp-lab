"""The calculator's web page: /pp-lab/ (index.html, app.css, app.js and an optional theme)."""
from __future__ import annotations

import html
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse, Response

from .. import config

router = APIRouter()
WEB = Path(__file__).resolve().parent

HEADERS = {
    "Content-Security-Policy": (
        "default-src 'self'; img-src 'self' https: data:; style-src 'self'; script-src 'self'; "
        "connect-src 'self'; font-src 'self' https: data:; frame-ancestors 'self'; base-uri 'none'; form-action 'none'"
    ),
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "X-Frame-Options": "SAMEORIGIN",
}


def _page() -> str:
    page = (WEB / "index.html").read_text(encoding="utf-8")
    name = html.escape(config.SITE_NAME)
    logo = f'<img src="{html.escape(config.SITE_LOGO, quote=True)}" alt="">' if config.SITE_LOGO else ""
    theme = '<link rel="stylesheet" href="assets/theme.css">' if config.THEME_CSS else ""
    return (
        page.replace("{{SITE_NAME}}", name)
        .replace("{{LOGO}}", logo)
        .replace("{{THEME_LINK}}", theme)
        .replace("{{COVER_URL}}", html.escape(config.COVER_URL, quote=True))
    )


@router.get("/", include_in_schema=False)
def home() -> Response:
    return RedirectResponse("/pp-lab/")


@router.get("/pp-lab", include_in_schema=False)
def no_slash() -> Response:
    return RedirectResponse("/pp-lab/")


@router.get("/pp-lab/", include_in_schema=False)
def index() -> Response:
    return HTMLResponse(_page(), headers=dict(HEADERS, **{"Cache-Control": "no-cache"}))


@router.get("/pp-lab/assets/{name}", include_in_schema=False)
def asset(name: str) -> Response:
    if name == "theme.css":
        if not config.THEME_CSS:
            raise HTTPException(404)
        path = Path(config.THEME_CSS)
        if not path.is_absolute():
            path = config.ROOT / path
        if not path.is_file():
            raise HTTPException(404)
        return FileResponse(path, media_type="text/css", headers=HEADERS)
    files = {"app.css": "text/css", "app.js": "application/javascript"}
    if name not in files:
        raise HTTPException(404)
    return FileResponse(WEB / name, media_type=files[name], headers=dict(HEADERS, **{"Cache-Control": "public, max-age=3600"}))
