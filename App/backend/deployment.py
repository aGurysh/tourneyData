"""Single-origin production app. Local development still uses backend.api.main."""

import base64
import binascii
import os
from pathlib import Path
import secrets

from starlette.datastructures import Headers
from starlette.responses import PlainTextResponse
from starlette.staticfiles import StaticFiles

from backend.config import APP_ROOT, load_settings
from backend.api.main import create_app


class PreviewAccess:
    """Protect pages, assets, API, and docs; expose only Render's health probe."""

    def __init__(self, app, *, username: str, password: str):
        self.app = app
        self.username = username.encode("utf-8")
        self.password = password.encode("utf-8")

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        if scope["path"] == "/health" and scope["method"] in {"GET", "HEAD"}:
            await self.app(scope, receive, send)
            return

        authorization = Headers(scope=scope).get("authorization", "")
        scheme, _, token = authorization.partition(" ")
        username = password = b""
        valid = False
        if scheme.lower() == "basic":
            try:
                decoded = base64.b64decode(token, validate=True)
                username, separator, password = decoded.partition(b":")
                valid = bool(separator)
            except (ValueError, binascii.Error):
                pass
        user_matches = secrets.compare_digest(username, self.username)
        password_matches = secrets.compare_digest(password, self.password)
        if not (valid and user_matches and password_matches):
            response = PlainTextResponse(
                "Authentication required", status_code=401,
                headers={
                    "WWW-Authenticate": 'Basic realm="Private preview", charset="UTF-8"',
                    "Cache-Control": "no-store",
                    "X-Robots-Tag": "noindex, nofollow",
                },
            )
            await response(scope, receive, send)
            return

        async def private_headers(message):
            if message["type"] == "http.response.start":
                headers = [(key, value) for key, value in message.get("headers", [])
                           if key.lower() not in {b"cache-control", b"x-robots-tag"}]
                headers.extend([(b"cache-control", b"no-store"),
                                (b"x-robots-tag", b"noindex, nofollow")])
                message = {**message, "headers": headers}
            await send(message)

        await self.app(scope, receive, private_headers)


def create_deployment_app(*, frontend_dir: Path | None = None):
    load_settings()
    mode = os.getenv("DEPLOYMENT_ACCESS", "private")
    if mode not in {"private", "public"}:
        raise RuntimeError("DEPLOYMENT_ACCESS must be private or public.")
    username = os.getenv("PREVIEW_USERNAME", "")
    password = os.getenv("PREVIEW_PASSWORD", "")
    if mode == "private" and (not username or ":" in username or not password):
        raise RuntimeError("Private deployment requires PREVIEW_USERNAME (without ':') and PREVIEW_PASSWORD.")

    directory = frontend_dir if frontend_dir is not None else APP_ROOT / "frontend" / "dist"
    if not (directory / "index.html").is_file():
        raise RuntimeError("Build the frontend before starting the deployment app.")
    app = create_app(api_prefix="/api")
    # The current UI has no client-side URL routes. Missing assets/API routes
    # must remain 404s rather than receiving index.html as an accidental fallback.
    app.mount("/", StaticFiles(directory=directory, html=True), name="frontend")
    if mode == "private":
        app.add_middleware(PreviewAccess, username=username, password=password)
    return app
