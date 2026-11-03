import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.errors import CodeResilienceError
from app.services.demo_service import ensure_demo_project

router = APIRouter(tags=["demo"])


class DemoEnsureFailedError(CodeResilienceError):
    code = "DEMO_ENSURE_FAILED"
    status_code = 500
    message = "Demo workspace setup failed."


class DemoOut(BaseModel):
    project_id: uuid.UUID
    analysis_run_id: uuid.UUID | None
    status: str
    created: bool


@router.post("/demo/ensure", response_model=DemoOut)
def ensure_demo(db: Session = Depends(get_db)):
    """Idempotent demo bootstrap: returns the existing fully-analyzed demo
    project when available, otherwise builds + analyzes a fresh one. Powers
    the frontend's one-click 'Load demo workspace' button so the demo is
    always available without running scripts."""
    result = ensure_demo_project(db)
    if result["status"] != "complete":
        raise DemoEnsureFailedError(f"Demo workspace setup failed (analysis status: {result['status']}).")
    return result
