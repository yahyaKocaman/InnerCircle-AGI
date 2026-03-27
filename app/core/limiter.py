"""
Rate Limiter — Security Layer
──────────────────────────────
Uses slowapi (Starlette-compatible) to prevent brute-force attacks.

Applied to:
  - POST /auth/register → 5 requests / minute per IP
  - POST /auth/login    → 10 requests / minute per IP
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

# Rate limiter keyed by client IP address
limiter = Limiter(key_func=get_remote_address)
