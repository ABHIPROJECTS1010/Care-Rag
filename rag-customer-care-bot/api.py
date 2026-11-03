"""
api.py — Care-RAG FastAPI backend
Comprehensive security hardening:
  - SEC-01: Strict path traversal prevention with Path.resolve().relative_to() & 403 on breakout
  - SEC-02: CORS restricted to explicit origin allowlist (env-configurable)
  - SEC-03: Per-IP rate limiting via slowapi
  - SEC-04: Per-session ChatSession with HttpOnly cookie isolation
  - SEC-07: Pydantic input length and content validation (1–2000 chars)
  - SEC-08: Security headers middleware (CSP, X-Frame-Options, X-Content-Type-Options, etc.)
  - SEC-09: Production TLS detection & configurable secure cookie flag
  - SEC-10: Memory-bounded session store with LRU eviction and thread locking
"""

import os
import threading
import time
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

# ── Per-session ChatSession store (SEC-04, SEC-08) ───────────────────────────
SESSION_COOKIE = "care_rag_session"
SESSION_TTL: int = int(os.getenv("SESSION_TTL_SECONDS", "3600"))  # 1 hour default
MAX_SESSIONS: int = int(os.getenv("MAX_SESSIONS", "5000"))         # Hard memory limit
COOKIE_SECURE: bool = (
    os.getenv("COOKIE_SECURE", "").lower() in ("true", "1", "yes")
    or os.getenv("ENVIRONMENT", "").lower() == "production"
)

# {session_id: {"obj": ChatSession, "last_seen": float}}
_sessions: dict[str, dict] = {}
_session_lock = threading.Lock()


def _get_or_create_session(session_id: Optional[str]) -> tuple[str, ChatSession]:
    """
    Return (session_id, ChatSession) for the given cookie value.
    Creates a fresh session when the ID is absent, expired, or invalid.
    Enforces TTL eviction and MAX_SESSIONS hard cap with LRU pruning to prevent memory exhaustion (SEC-08).
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
        new_id = str(uuid.uuid4())
        _sessions[new_id] = {"obj": ChatSession(), "last_seen": now}
        return new_id, _sessions[new_id]["obj"]


def _set_session_cookie(response: Response, session_id: str, request: Optional[Request] = None) -> None:
    """
    Write a secure, httpOnly session cookie to the response.
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
    if session_id:
        with _session_lock:
            if session_id in _sessions:
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

        SEC-01 fix: resolve path and assert it stays strictly inside
        FRONTEND_DIST before serving. Returns 403 on traversal attempt.
        """
        if full_path:
            safe_path = full_path.lstrip("/\\")
            try:
                target = (FRONTEND_DIST / safe_path).resolve()
                target.relative_to(FRONTEND_DIST)  # Raises ValueError if outside
                if target.is_file():
                    return FileResponse(str(target))
            except ValueError:
                raise HTTPException(status_code=403, detail="Access denied: path traversal attempt detected.")

        index_file = FRONTEND_DIST / "index.html"
        if index_file.exists():
            return FileResponse(str(index_file))
        return {"status": "online", "message": "Frontend build not deployed"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("api:app", host="127.0.0.1", port=8000)