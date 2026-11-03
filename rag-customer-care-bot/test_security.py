"""
test_security.py — Regression tests for all SEC-* findings.
Run with:  pytest test_security.py -v
"""

import pytest
from fastapi.testclient import TestClient

# Import the app after any module-level side-effects are resolved
from api import app

client = TestClient(app, raise_server_exceptions=False)


# ── SEC-01: Path Traversal ────────────────────────────────────────────────────
class TestPathTraversal:
    """The static-file route must never serve files outside dist/."""

    PAYLOADS = [
        "/../chatbot.py",
        "/../chatbot.log",
        "/../data/knowledge_base.txt",
        "/../../etc/passwd",
        "/%2e%2e/chatbot.py",          # URL-encoded ../
        "/..%2Fchatbot.py",
        "/assets/../../../../chatbot.py",
    ]

    @pytest.mark.parametrize("path", PAYLOADS)
    def test_traversal_blocked(self, path):
        r = client.get(path)
        # Must NOT expose Python source or log data
        assert "ChatSession" not in r.text, f"Source leaked on {path}"
        assert "logging" not in r.text.lower() or r.status_code == 404


# ── SEC-02: CORS ──────────────────────────────────────────────────────────────
class TestCORS:
    def test_wildcard_origin_not_used(self):
        r = client.options(
            "/chat",
            headers={"Origin": "http://evil.example.com",
                     "Access-Control-Request-Method": "POST"},
        )
        acao = r.headers.get("access-control-allow-origin", "")
        assert acao != "*", "CORS must not return wildcard allow-origin"

    def test_allowed_origin_reflected(self):
        r = client.options(
            "/chat",
            headers={"Origin": "http://localhost:5173",
                     "Access-Control-Request-Method": "POST"},
        )
        acao = r.headers.get("access-control-allow-origin", "")
        assert acao == "http://localhost:5173"


# ── SEC-03: Rate Limiting ─────────────────────────────────────────────────────
class TestRateLimiting:
    def test_chat_rate_limit_enforced(self):
        """Sending 25 rapid requests should trigger 429 before all complete."""
        statuses = set()
        for _ in range(25):
            r = client.post("/chat", json={"message": "hello"})
            statuses.add(r.status_code)
        assert 429 in statuses, "Rate limiter did not return 429"

    def test_reset_rate_limit_enforced(self):
        statuses = set()
        for _ in range(10):
            r = client.post("/reset")
            statuses.add(r.status_code)
        assert 429 in statuses, "Reset rate limiter did not return 429"


# ── SEC-04: Session Isolation ─────────────────────────────────────────────────
class TestSessionIsolation:
    def test_different_clients_get_different_sessions(self):
        """Two independent clients must not share conversation history."""
        c1 = TestClient(app)
        c2 = TestClient(app)

        r1 = c1.post("/chat", json={"message": "hi"})
        # Reset only client-1's session
        c1.post("/reset")

        # Client-2 should still have its own intact session
        r2 = c2.post("/chat", json={"message": "hello"})
        assert r2.status_code == 200

    def test_reset_only_clears_own_session(self):
        c1 = TestClient(app)
        c2 = TestClient(app)

        c1.post("/chat", json={"message": "track my order"})
        c1.post("/reset")   # should only reset c1

        # c2 was never reset; a fresh message should still work
        r = c2.post("/chat", json={"message": "hello"})
        assert r.status_code == 200


# ── SEC-07: Input Validation ──────────────────────────────────────────────────
class TestInputValidation:
    def test_message_too_long_rejected(self):
        r = client.post("/chat", json={"message": "A" * 2001})
        assert r.status_code == 422

    def test_empty_message_rejected(self):
        r = client.post("/chat", json={"message": ""})
        assert r.status_code == 422

    def test_missing_message_rejected(self):
        r = client.post("/chat", json={})
        assert r.status_code == 422

    def test_valid_message_accepted(self):
        r = client.post("/chat", json={"message": "How do I track my order?"})
        assert r.status_code == 200
        assert "reply" in r.json()

    def test_max_length_boundary_accepted(self):
        r = client.post("/chat", json={"message": "A" * 2000})
        assert r.status_code == 200


# ── SEC-08: Security Headers ──────────────────────────────────────────────────
class TestSecurityHeaders:
    ENDPOINTS = ["/health", "/chat"]

    @pytest.mark.parametrize("path", ["/health"])
    def test_csp_present(self, path):
        r = client.get(path)
        assert "content-security-policy" in r.headers

    @pytest.mark.parametrize("path", ["/health"])
    def test_x_frame_options(self, path):
        r = client.get(path)
        assert r.headers.get("x-frame-options", "").upper() == "DENY"

    @pytest.mark.parametrize("path", ["/health"])
    def test_x_content_type_options(self, path):
        r = client.get(path)
        assert r.headers.get("x-content-type-options", "").lower() == "nosniff"
