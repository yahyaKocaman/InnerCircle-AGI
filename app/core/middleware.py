"""
Security & Observability Middleware
────────────────────────────────────
• SecurityHeadersMiddleware  → OWASP-recommended HTTP headers on every response
• RequestLoggingMiddleware   → Structured request/response logging with duration
"""

import time
import logging
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger(__name__)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Adds OWASP-recommended security headers to every HTTP response.

    Headers added:
    - X-Content-Type-Options   → Prevents MIME-type sniffing
    - X-Frame-Options          → Prevents clickjacking
    - X-XSS-Protection         → Legacy XSS filter hint for older browsers
    - Referrer-Policy          → Controls referrer information
    - Permissions-Policy       → Restricts browser features
    - Strict-Transport-Security→ Enforces HTTPS (HSTS)
    """

    HEADERS = {
        "X-Content-Type-Options":    "nosniff",
        "X-Frame-Options":           "DENY",
        "X-XSS-Protection":          "1; mode=block",
        "Referrer-Policy":           "strict-origin-when-cross-origin",
        "Permissions-Policy":        "geolocation=(), microphone=(), camera=()",
        "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
    }

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        for header, value in self.HEADERS.items():
            response.headers[header] = value
        return response


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    Logs every HTTP request with:
    - HTTP method & path
    - Response status code
    - Duration in milliseconds
    - Client IP address

    This is the observability layer — logs can be shipped to
    Loki / ELK / CloudWatch for centralized analysis.
    """

    # Skip noisy paths from logs
    SKIP_PATHS = {"/metrics", "/health", "/static"}

    async def dispatch(self, request: Request, call_next) -> Response:
        # Skip health/metrics polling to keep logs clean
        if request.url.path in self.SKIP_PATHS:
            return await call_next(request)

        start = time.perf_counter()
        response = await call_next(request)
        duration_ms = round((time.perf_counter() - start) * 1000, 2)

        # Structured log — compatible with Loki / Datadog JSON ingestion
        logger.info(
            "request completed",
            extra={
                "http_method":  request.method,
                "http_path":    request.url.path,
                "http_status":  response.status_code,
                "duration_ms":  duration_ms,
                "client_ip":    getattr(request.client, "host", "unknown"),
            },
        )
        return response
