from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.db import get_db

router = APIRouter(tags=["health"])


@router.get("/health")
def health_check() -> dict:
    return {"status": "ok"}


@router.get("/health/live")
def liveness() -> dict:
    return {"status": "alive"}


@router.get("/health/ready")
def readiness(db: Session = Depends(get_db)) -> dict:
    try:
        db.execute(text("SELECT 1"))
        return {
            "status": "ready",
            "database": "connected",
        }
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Database connection check failed: {str(exc)}",
        )
