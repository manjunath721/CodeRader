import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.errors import CodeResilienceError
from app.models.developer import Developer
from app.models.simulation import Simulation, SimulationResult
from app.schemas.analytics import SimulationOut, SimulationRequest
from app.services.query_service import get_project_or_404
from app.services.simulation_service import run_simulation

router = APIRouter(tags=["simulations"])


class SimulationNotFoundError(CodeResilienceError):
    code = "SIMULATION_NOT_FOUND"
    status_code = 404
    message = "Simulation not found."


@router.post("/simulations/developer-unavailability", response_model=SimulationOut)
def simulate_developer_unavailability(payload: SimulationRequest, db: Session = Depends(get_db)):
    project = get_project_or_404(db, payload.project_id)
    dev_ids = [payload.developer_id] if payload.developer_id else (payload.developer_ids or [])
    if dev_ids:
        valid_devs = {
            d[0] for d in db.query(Developer.id).filter(Developer.project_id == project.id, Developer.id.in_(dev_ids)).all()
        }
        invalid = [d for d in dev_ids if d not in valid_devs]
        if invalid:
            raise HTTPException(
                status_code=400,
                detail=f"Developer ID(s) {[str(i) for i in invalid]} do not belong to project {project.id}."
            )
    return run_simulation(db, project, dev_ids)


@router.post("/simulations/multiple-failure", response_model=SimulationOut)
def simulate_multiple_failure(payload: SimulationRequest, db: Session = Depends(get_db)):
    project = get_project_or_404(db, payload.project_id)
    dev_ids = payload.developer_ids or ([payload.developer_id] if payload.developer_id else [])
    if dev_ids:
        valid_devs = {
            d[0] for d in db.query(Developer.id).filter(Developer.project_id == project.id, Developer.id.in_(dev_ids)).all()
        }
        invalid = [d for d in dev_ids if d not in valid_devs]
        if invalid:
            raise HTTPException(
                status_code=400,
                detail=f"Developer ID(s) {[str(i) for i in invalid]} do not belong to project {project.id}."
            )
    return run_simulation(db, project, dev_ids)


@router.get("/simulations/{simulation_id}")
def get_simulation(simulation_id: uuid.UUID, db: Session = Depends(get_db)):
    sim = db.get(Simulation, simulation_id)
    if not sim:
        raise SimulationNotFoundError()
    result = db.query(SimulationResult).filter(SimulationResult.simulation_id == sim.id).first()
    return {
        "simulation_id": sim.id, "type": sim.type, "developer_ids": sim.developer_ids,
        "requested_at": sim.requested_at, "result": {
            "resilience_before": result.resilience_before, "resilience_after": result.resilience_after,
            "knowledge_impact_pct": result.knowledge_impact_pct, "affected_modules": result.affected_modules,
            "backup_candidates": result.backup_candidates, "risk_propagation": result.risk_propagation,
        } if result else None,
    }


@router.get("/projects/{project_id}/simulations")
def list_simulations(project_id: uuid.UUID, db: Session = Depends(get_db)):
    get_project_or_404(db, project_id)
    sims = db.query(Simulation).filter(Simulation.project_id == project_id).order_by(Simulation.requested_at.desc()).all()
    out = []
    for sim in sims:
        result = db.query(SimulationResult).filter(SimulationResult.simulation_id == sim.id).first()
        out.append(
            {
                "simulation_id": sim.id, "type": sim.type, "developer_ids": sim.developer_ids,
                "requested_at": sim.requested_at,
                "resilience_before": result.resilience_before if result else None,
                "resilience_after": result.resilience_after if result else None,
            }
        )
    return out
