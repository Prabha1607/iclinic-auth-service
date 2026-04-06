from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI
from starlette.middleware.base import BaseHTTPMiddleware

from src.api.middleware.auth import AuthorizationMiddleware
from src.api.middleware.cors import add_cors_middleware
from src.api.middleware.logging import logging_middleware, setup_logging
from src.api.rest.routes import auth, health, internal, users
# from src.data.clients.postgres_client import init_db
# from src.data.seeds.seed_appointment_types import seed_appointment_types
# from src.data.seeds.seed_doctors import seed_doctors
# from src.data.seeds.seed_roles import seed_roles
# from src.data.seeds.seed_users import seed_users
from src.core.exceptions.base import AppError
from src.config.rate_limit import limiter
from slowapi.errors import RateLimitExceeded
from slowapi import _rate_limit_exceeded_handler
from fastapi.responses import JSONResponse
from prometheus_fastapi_instrumentator import Instrumentator
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    # await init_db()
    # await seed_roles()  # users depend on roles
    # await seed_appointment_types()  # users depend on appointment types
    # await seed_users()  # now users can reference both
    # await seed_doctors()  # doctors likely reference users
    yield


app = FastAPI(lifespan=lifespan, title="Auth Service", version="1.0.0")

app.add_middleware(AuthorizationMiddleware)
app.add_middleware(BaseHTTPMiddleware, dispatch=logging_middleware)

add_cors_middleware(app)

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(router=auth.router)
api_router.include_router(router=users.router)
api_router.include_router(router=health.router)
api_router.include_router(router=internal.router)
app.include_router(router=api_router)

@app.exception_handler(AppError)
async def app_error_handler(request, exc: AppError):
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.message})

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

Instrumentator().instrument(app).expose(app)
try:
    FastAPIInstrumentor.instrument_app(app)
except Exception:
    pass
