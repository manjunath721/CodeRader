import uuid
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.router import api_router
from app.core.config import get_settings
from app.core.errors import CodeResilienceError
from app.services.job_worker import recover_stale_runs_on_startup
from app.services.scheduler import start_scheduler, stop_scheduler

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup actions: clean orphan runs from unexpected restarts & start scheduler
    recover_stale_runs_on_startup()
    start_scheduler()
    yield
    # Shutdown actions
    stop_scheduler()


app = FastAPI(
    title=settings.APP_NAME,
    description="Repository Intelligence & Software Engineering Risk Analysis Platform",
    version="0.1.0",
    debug=settings.DEBUG,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def security_and_correlation_headers(request: Request, call_next):
    request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
    response: Response = await call_next(request)
    response.headers["x-request-id"] = request_id
    response.headers["x-content-type-options"] = "nosniff"
    response.headers["x-frame-options"] = "DENY"
    response.headers["x-xss-protection"] = "1; mode=block"
    response.headers["strict-transport-security"] = "max-age=31536000; includeSubDomains"
    return response


@app.exception_handler(CodeResilienceError)
def handle_coderesilience_error(request: Request, exc: CodeResilienceError) -> JSONResponse:
    # Never leak stack traces to the client (§43) — only the curated message + code.
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.message, "code": exc.code},
    )


app.include_router(api_router, prefix=settings.API_V1_PREFIX)


@app.get("/")
def root() -> dict:
    return {"name": settings.APP_NAME, "status": "running", "docs": "/docs"}
