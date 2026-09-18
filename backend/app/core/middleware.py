import logging
import re
import time
import uuid

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.logging import request_id_ctx

logger = logging.getLogger("app.request")

_VALID_REQUEST_ID = re.compile(r"^[A-Za-z0-9._-]{1,64}$")


class RequestContextMiddleware:
    """
    Assigns a request ID (reusing a sane incoming X-Request-ID), exposes it in the
    response header, and logs one line per request with status and duration.

    Pure ASGI (not BaseHTTPMiddleware) so streaming responses are not buffered.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        incoming = dict(scope["headers"]).get(b"x-request-id", b"").decode("latin-1")
        request_id = incoming if _VALID_REQUEST_ID.match(incoming) else uuid.uuid4().hex
        token = request_id_ctx.set(request_id)

        status_code = 500
        start = time.perf_counter()

        async def send_wrapper(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
                message.setdefault("headers", []).append((b"x-request-id", request_id.encode()))
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            duration_ms = round((time.perf_counter() - start) * 1000, 1)
            logger.info(
                "%s %s -> %s (%sms)",
                scope["method"],
                scope["path"],
                status_code,
                duration_ms,
                extra={
                    "method": scope["method"],
                    "path": scope["path"],
                    "status": status_code,
                    "duration_ms": duration_ms,
                },
            )
            request_id_ctx.reset(token)


class SecurityHeadersMiddleware:
    """Adds standard hardening headers to every response."""

    def __init__(self, app: ASGIApp, hsts: bool) -> None:
        self.app = app
        self.headers = [
            (b"x-content-type-options", b"nosniff"),
            (b"x-frame-options", b"DENY"),
            (b"referrer-policy", b"strict-origin-when-cross-origin"),
            (b"cross-origin-opener-policy", b"same-origin"),
            # The API serves JSON and PDFs only; nothing should execute in its origin
            (b"content-security-policy", b"default-src 'none'; frame-ancestors 'none'"),
        ]
        if hsts:  # only meaningful (and safe) when served over HTTPS
            self.headers.append((b"strict-transport-security", b"max-age=31536000; includeSubDomains"))

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_wrapper(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = message.get("headers", [])
                existing = {k.lower() for k, _ in headers}
                content_type = next((v for k, v in headers if k.lower() == b"content-type"), b"")
                # Strict CSP only on JSON: Swagger UI (HTML) needs its CDN assets and
                # browsers' built-in PDF viewers can break under default-src 'none'
                wants_csp = content_type.startswith(b"application/json")
                extra = [
                    (k, v)
                    for k, v in self.headers
                    if k not in existing and (wants_csp or k != b"content-security-policy")
                ]
                message["headers"] = [*headers, *extra]
            await send(message)

        await self.app(scope, receive, send_wrapper)
