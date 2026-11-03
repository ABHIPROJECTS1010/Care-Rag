"""
api.py — Care-RAG FastAPI backend
Security hardening applied:
  - SEC-01: Path traversal fixed with Path.resolve().relative_to() containment
  - SEC-02: CORS restricted to explicit origin allowlist (env-configurable)
  - SEC-03: Per-IP rate limiting via slowapi
  - SEC-04: Per-session ChatSession with httponly cookie isolation
  - SEC-07: Pydantic input length validation (1–2000 chars)
  - SEC-08: Security headers middleware (CSP, X-Frame-Options, etc.)
"""

import os
import time
import uuid
from pathlib import Path
from typing import Optional

from fastapi import Cookie, FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from starlette.middleware.base import BaseHTTPMiddleware

from chatbot import ChatSession

# ── Rate limiter (SEC-03) ────────────────────────────────────────────────────
limiter = Limiter(key_func=get_remote_address)

app = FastAPI(title="Care-RAG Support Chatbot API")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


# ── Security headers middleware (SEC-08) ─────────────────────────────────────
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Adds defence-in-depth HTTP security headers to every response."""

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        # Content-Security-Policy: restrict resource origins
        # 'unsafe-inline' for style-src is required by the React app's inline styles.
        # Remove it when inline styles are moved to external CSS.
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: blob:; "
            "connect-src 'self'; "
            "worker-src blob:; "
            "frame-ancestors 'none';"
        )
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = (
            "geolocation=(), microphone=(), camera=()"
        )
        return response


app.add_middleware(SecurityHeadersMiddleware)

# ── CORS — restricted to an explicit allowlist (SEC-02) ──────────────────────
# Override via environment variable for production deployments, e.g.:
#   CORS_ALLOWED_ORIGINS="https://yourapp.example.com"
_raw_origins = os.getenv(
    "CORS_ALLOWED_ORIGINS",
    "http://localhost:5173,http://localhost:8000,"
    "http://127.0.0.1:5173,http://127.0.0.1:8000",
)
ALLOWED_ORIGINS: list[str] = [o.strip() for o in _raw_origins.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,          # explicit list, never wildcard
    allow_credentials=True,                  # required for session cookies
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)

# ── Per-session ChatSession store (SEC-04) ───────────────────────────────────
SESSION_COOKIE = "care_rag_session"
SESSION_TTL: int = int(os.getenv("SESSION_TTL_SECONDS", "3600"))  # 1 hour default

# {session_id: {"obj": ChatSession, "last_seen": float}}
_sessions: dict[str, dict] = {}


def _get_or_create_session(session_id: Optional[str]) -> tuple[str, ChatSession]:
    """
    Return (session_id, ChatSession) for the given cookie value.
    Creates a fresh session when the ID is absent or expired.
    Also evicts sessions older than SESSION_TTL.
    """
    now = time.monotonic()

    # Evict expired sessions to prevent unbounded memory growth
    expired = [
        sid
        for sid, data in _sessions.items()
        if now - data["last_seen"] > SESSION_TTL
    ]
    for sid in expired:
        del _sessions[sid]

    if session_id and session_id in _sessions:
        _sessions[session_id]["last_seen"] = now
        return session_id, _sessions[session_id]["obj"]

    new_id = str(uuid.uuid4())
    _sessions[new_id] = {"obj": ChatSession(), "last_seen": now}
    return new_id, _sessions[new_id]["obj"]


def _set_session_cookie(response: Response, session_id: str) -> None:
    """Write a secure, httpOnly session cookie to the response."""
    response.set_cookie(
        key=SESSION_COOKIE,
        value=session_id,
        max_age=SESSION_TTL,
        httponly=True,          # not readable by JavaScript
        samesite="strict",      # no cross-site sending
        # secure=True when the service is behind HTTPS (recommended for production)
        secure=False,
    )


# ── Request / Response models (SEC-07) ───────────────────────────────────────
class ChatRequest(BaseModel):
    message: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="User message — must be between 1 and 2 000 characters.",
    )


class ChatResponse(BaseModel):
    reply: str


# ── Routes ───────────────────────────────────────────────────────────────────
@app.get("/health")
def health():
    return {
        "status": "online",
        "service": "Care-RAG Support Chatbot API",
        "version": "1.0.0",
    }


@app.post("/chat", response_model=ChatResponse)
@limiter.limit("20/minute")
def chat(
    request: Request,
    response: Response,
    body: ChatRequest,
    session_id: Optional[str] = Cookie(default=None, alias=SESSION_COOKIE),
):
    """Send a message and receive a RAG-grounded answer. (20 req/min per IP)"""
    sid, session = _get_or_create_session(session_id)
    if sid != session_id:
        _set_session_cookie(response, sid)
    answer = session.get_answer(body.message)
    return ChatResponse(reply=answer)


@app.post("/reset")
@limiter.limit("5/minute")
def reset(
    request: Request,
    session_id: Optional[str] = Cookie(default=None, alias=SESSION_COOKIE),
):
    """Clear the calling user's own conversation history. (5 req/min per IP)"""
    if session_id and session_id in _sessions:
        _sessions[session_id]["obj"].reset()
    return {"status": "success", "message": "Chat history cleared"}


# ── Serve built frontend (SEC-01 path traversal fix) ─────────────────────────
FRONTEND_DIST = Path(
    os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "rag-chatbot-frontend", "dist")
    )
)

if FRONTEND_DIST.exists():
    assets_path = FRONTEND_DIST / "assets"
    if assets_path.exists():
        app.mount(
            "/assets", StaticFiles(directory=str(assets_path)), name="assets"
        )

    @app.get("/{full_path:path}")
    def serve_frontend(full_path: str = ""):
        """
        Serve the React SPA from the dist directory.

        SEC-01 fix: resolve the full path and assert it stays strictly inside
        FRONTEND_DIST before serving.  Path.relative_to() raises ValueError for
        any attempt to escape the directory (e.g. '../../etc/passwd').
        """
        if full_path:
            try:
                target = (FRONTEND_DIST / full_path).resolve()
                target.relative_to(FRONTEND_DIST)  # ValueError if outside
                if target.is_file():
                    return FileResponse(str(target))
            except ValueError:
                # Path traversal attempt detected — silently fall through to SPA
                pass
        return FileResponse(str(FRONTEND_DIST / "index.html"))


if __name__ == "__main__":
    import uvicorn

    # Note: --reload is intentionally omitted here (development feature only).
    # Use `uvicorn api:app --reload` explicitly during local development.
    uvicorn.run("api:app", host="127.0.0.1", port=8000)