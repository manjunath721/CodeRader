from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.ai.analyst import answer_question
from app.core.db import get_db
from app.schemas.analytics import AIQueryRequest, AIQueryResponse
from app.services.query_service import get_project_or_404

router = APIRouter(tags=["ai"])


@router.post("/ai/query", response_model=AIQueryResponse)
def ai_query(payload: AIQueryRequest, db: Session = Depends(get_db)):
    project = get_project_or_404(db, payload.project_id)
    return answer_question(db, project, payload.question)
