"""Bearer-token authentication for the desktop sidecar.

The Electron shell generates a random token per launch and passes it to the
backend process, so a local port scan cannot drive the API. When no token is
configured (plain ``docker compose`` use) the middleware is not installed.
"""

from __future__ import annotations

import hmac

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response


class BearerTokenMiddleware(BaseHTTPMiddleware):
    """Reject requests whose Authorization header does not match the token."""

    def __init__(self, app, token: str) -> None:
        super().__init__(app)
        self._expected = f"Bearer {token}"

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        provided = request.headers.get("Authorization", "")
        # Constant-time comparison so a local attacker cannot recover the token
        # byte-by-byte from response timing.
        if not hmac.compare_digest(provided, self._expected):
            return JSONResponse(status_code=401, content={"detail": "Unauthorized"})
        return await call_next(request)
