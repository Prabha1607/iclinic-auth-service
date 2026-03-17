from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from src.config.jwt_handler import verify_access_token


class AuthorizationMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):

        public_paths = [
            "/",
            "/api/v1/auth/login",
            "/api/v1/auth/register",
            "/api/v1/auth/refresh",
            "/api/v1/auth/verify",
            "/api/v1/users/get_roles",
            "/api/v1/users/patients/create",
            "/api/v1/health",
            "/favicon.ico",
            "/docs",
            "/openapi.json",
        ]

        if request.url.path.startswith("/api/v1/internal/"):
            return await call_next(request)

        if request.url.path in public_paths or request.method == "OPTIONS":
            return await call_next(request)

        credential = request.headers.get("Authorization")

        if credential is None:
            return JSONResponse(
                status_code=400,
                content={"detail": "Bearer authorization required"},
            )

        scheme, _, token = credential.partition(" ")

        if scheme.lower() != "bearer":
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid authorization scheme. Expected Bearer."},
            )

        try:
            access_payload = await verify_access_token(token)
        except Exception:
            access_payload = None

        if access_payload is None:
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid or expired token."},
            )

        return await call_next(request)
