from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.router import api_router
from app.core.config import get_settings
from app.core.errors import CodeResilienceError

settings = get_settings()

app = FastAPI(
    title=settings.APP_NAME,
    description="AI-Powered Software Team Knowledge & Risk Analyzer",
    version="0.1.0",
    debug=settings.DEBUG,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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
