"""
api.py — Care-RAG FastAPI backend
Comprehensive security hardening:
  - SEC-01: Strict path traversal prevention with Path.resolve().relative_to() & 403 on breakout
  - SEC-02: CORS restricted to explicit origin allowlist (env-configurable)
  - SEC-03: Per-IP rate limiting via slowapi
  - SEC-04: Per-session ChatSession with HttpOnly cookie isolation
  - SEC-07: Pydantic input length and content validation (1–2000 chars, rejects blank/whitespace)
  - SEC-08: Security headers middleware (CSP, X-Frame-Options, X-Content-Type-Options, etc.)
  - SEC-09: Production TLS detection & configurable secure cookie flag
  - SEC-10: Memory-bounded session store with LRU eviction and thread locking
"""

import os
import re
import threading
import time
import urllib.parse
import uuid
from pathlib import Path
from typing import Optional

from fastapi import Cookie, FastAPI, HTTPException, Request, Response
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
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: blob:; "
            "connect-src 'self' http://localhost:8000 http://127.0.0.1:8000; "
            "worker-src blob:; "
            "frame-ancestors 'none'; "
            "base-uri 'self'; "
            "form-action 'self';"
        )
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = (
            "geolocation=(), microphone=(), camera=()"
        )
        response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
        response.headers["Cross-Origin-Resource-Policy"] = "same-origin"
        response.headers["X-Permitted-Cross-Domain-Policies"] = "none"

        # Enforce HSTS in production or over HTTPS
        if COOKIE_SECURE or request.url.scheme == "https" or request.headers.get("x-forwarded-proto", "").lower() == "https":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

        # Suppress server signature header
        if "server" in response.headers:
            del response.headers["server"]

        return response


app.add_middleware(SecurityHeadersMiddleware)

# ── CORS — restricted to an explicit allowlist (SEC-02) ──────────────────────
_raw_origins = os.getenv(
    "CORS_ALLOWED_ORIGINS",
    "http://localhost:5173,http://localhost:8000,"
    "http://127.0.0.1:5173,http://127.0.0.1:8000",
)
ALLOWED_ORIGINS: list[str] = [o.strip() for o in _raw_origins.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,          # explicit list, never wildcard
    allow_credentials=True,                 # required for session cookies
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type"],
)

# ── Per-session ChatSession store (SEC-04, SEC-08, SEC-10) ───────────────────
SESSION_COOKIE = "care_rag_session"
SESSION_TTL: int = int(os.getenv("SESSION_TTL_SECONDS", "3600"))  # 1 hour default
MAX_SESSIONS: int = int(os.getenv("MAX_SESSIONS", "5000"))        # Hard memory limit
COOKIE_SECURE: bool = (
    os.getenv("COOKIE_SECURE", "").lower() in ("true", "1", "yes")
    or os.getenv("ENVIRONMENT", "").lower() == "production"
)

# {session_id: {"obj": ChatSession, "last_seen": float}}
_sessions: dict[str, dict] = {}
_session_lock = threading.Lock()


def _is_safe_session_id(sid: Optional[str]) -> bool:
    """Validate that session ID contains only safe alphanumeric and hyphen/underscore characters."""
    if not sid or not isinstance(sid, str):
        return False
    if len(sid) > 128:
        return False
    return bool(re.match(r"^[a-zA-Z0-9_\-]+$", sid))


def _get_or_create_session(session_id: Optional[str]) -> tuple[str, ChatSession]:
    """
    Return (session_id, ChatSession) for the given cookie value.
    Creates a fresh session when the ID is absent, expired, or invalid.
    Enforces TTL eviction and MAX_SESSIONS hard cap with LRU pruning to prevent memory exhaustion (SEC-08, SEC-10).
    Thread-safe using _session_lock.
    """
    now = time.monotonic()
    with _session_lock:
        # 1. Evict expired sessions
        expired = [
            sid
            for sid, data in _sessions.items()
            if now - data["last_seen"] > SESSION_TTL
        ]
        for sid in expired:
            del _sessions[sid]

        # 2. Re-use existing valid session
        if session_id and session_id in _sessions:
            _sessions[session_id]["last_seen"] = now
            return session_id, _sessions[session_id]["obj"]

        # 3. Enforce hard session capacity limit (LRU eviction)
        if len(_sessions) >= MAX_SESSIONS:
            num_to_prune = max(1, len(_sessions) // 10)
            sorted_by_age = sorted(_sessions.items(), key=lambda item: item[1]["last_seen"])
            for old_sid, _ in sorted_by_age[:num_to_prune]:
                _sessions.pop(old_sid, None)

        # 4. Create new isolated session
        new_id = session_id if (_is_safe_session_id(session_id) and session_id) else str(uuid.uuid4())
        _sessions[new_id] = {"obj": ChatSession(), "last_seen": now}
        return new_id, _sessions[new_id]["obj"]


def _set_session_cookie(response: Response, session_id: str, request: Optional[Request] = None) -> None:
    """
    Write a secure, HttpOnly session cookie to the response.
    Automatically applies secure=True if running on HTTPS or production (SEC-09).
    """
    is_https = COOKIE_SECURE
    if request is not None and not is_https:
        scheme = request.url.scheme
        forwarded_proto = request.headers.get("x-forwarded-proto", "")
        if scheme == "https" or forwarded_proto.lower() == "https":
            is_https = True

    response.set_cookie(
        key=SESSION_COOKIE,
        value=session_id,
        max_age=SESSION_TTL,
        httponly=True,          # not readable by JavaScript (XSS mitigation)
        samesite="lax",         # protects against CSRF while allowing standard navigation
        secure=is_https,        # dynamic HTTPS / production detection
        path="/",
    )


# ── Request / Response models (SEC-07) ───────────────────────────────────────
class ChatRequest(BaseModel):
    message: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="User message — must be between 1 and 2 000 characters.",
    )

    try:
        from pydantic import field_validator

        @field_validator("message", mode="before")
        @classmethod
        def check_not_blank(cls, v):
            if isinstance(v, str) and not v.strip():
                raise ValueError("Message cannot be empty or contain only whitespace.")
            return v
    except ImportError:
        from pydantic import validator

        @validator("message")
        def check_not_blank(cls, v):
            if isinstance(v, str) and not v.strip():
                raise ValueError("Message cannot be empty or contain only whitespace.")
            return v


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
    safe_sid = session_id if _is_safe_session_id(session_id) else None
    sid, session = _get_or_create_session(safe_sid)
    _set_session_cookie(response, sid, request=request)
    answer = session.get_answer(body.message)
    return ChatResponse(reply=answer)


@app.post("/reset")
@limiter.limit("5/minute")
def reset(
    request: Request,
    session_id: Optional[str] = Cookie(default=None, alias=SESSION_COOKIE),
):
    """Clear the calling user's own conversation history. (5 req/min per IP)"""
    safe_sid = session_id if _is_safe_session_id(session_id) else None
    if safe_sid:
        with _session_lock:
            if safe_sid in _sessions:
                _sessions[safe_sid]["obj"].reset()
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


def _is_traversal_attempt(path_str: str) -> bool:
    """Detect path traversal payloads across raw, single, and double URL-encoded forms."""
    decoded = urllib.parse.unquote(path_str)
    double_decoded = urllib.parse.unquote(decoded)
    for p in (path_str, decoded, double_decoded):
        if ".." in p or "\x00" in p or p.startswith("/") or p.startswith("\\"):
            return True
        if ":" in p:
            return True
    return False


@app.get("/{full_path:path}")
def serve_frontend(full_path: str = ""):
    """
    Serve the React SPA from the dist directory with strict directory traversal prevention (SEC-01).
    Returns 403 Forbidden on any traversal breakout attempt.
    """
    if full_path:
        if _is_traversal_attempt(full_path):
            raise HTTPException(status_code=403, detail="Access denied: path traversal attempt detected.")

        safe_path = full_path.lstrip("/\\")
        try:
            dist_base = FRONTEND_DIST.resolve()
            target = (dist_base / safe_path).resolve()
            # Strict boundary containment check
            target.relative_to(dist_base)
            if target.is_file():
                return FileResponse(str(target))
            # Return 404 for specific missing assets with extensions
            if Path(safe_path).suffix:
                raise HTTPException(status_code=404, detail="File not found")
        except ValueError:
            raise HTTPException(status_code=403, detail="Access denied: path traversal attempt detected.")

    index_file = FRONTEND_DIST / "index.html"
    if index_file.exists():
        return FileResponse(str(index_file))
    return Response(
        content='{"status":"online","message":"Frontend build not deployed"}',
        media_type="application/json",
        status_code=404 if full_path else 200,
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("api:app", host="127.0.0.1", port=8000)
