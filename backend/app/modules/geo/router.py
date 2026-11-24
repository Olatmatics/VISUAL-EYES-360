from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db.base import get_db
from app.models.auth import User
from app.models.core import LGA, FuelProduct, Station, State

router = APIRouter(prefix="/api/v1/geo", tags=["geo"])


@router.get("/states")
def list_states(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    counts = dict(
        db.execute(
            select(LGA.state_id, func.count(LGA.id)).group_by(LGA.state_id)
        ).all()
    )
    states = db.scalars(select(State).order_by(State.name)).all()
    return [
        {
            "id": state.id,
            "name": state.name,
            "code": state.code,
            "lga_count": counts.get(state.id, 0),
        }
        for state in states
    ]


@router.get("/states/{state_id}/lgas")
def list_state_lgas(
    state_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    state = db.scalar(select(State).where(State.id == state_id))
    if state is None:
        raise HTTPException(status_code=404, detail="State not found")
    lgas = db.scalars(select(LGA).where(LGA.state_id == state_id).order_by(LGA.name)).all()
    return [{"id": lga.id, "name": lga.name, "state_id": lga.state_id} for lga in lgas]


@router.get("/lgas")
def list_lgas(
    state_id: str | None = Query(default=None),
    search: str | None = Query(default=None),
    limit: int = Query(default=100, le=500),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    query = select(LGA)
    if state_id:
        query = query.where(LGA.state_id == state_id)
    if search:
        query = query.where(LGA.name.ilike(f"%{search.strip()}%"))
    lgas = db.scalars(query.order_by(LGA.name).limit(limit)).all()
    return [{"id": lga.id, "name": lga.name, "state_id": lga.state_id} for lga in lgas]


@router.get("/products")
def list_products(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    products = db.scalars(select(FuelProduct).order_by(FuelProduct.code)).all()
    return [{"id": p.id, "code": p.code, "name": p.name} for p in products]


@router.get("/overview")
def coverage_overview(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """National coverage counts used by dashboards and registration screens."""
    states = db.scalar(select(func.count(State.id))) or 0
    lgas = db.scalar(select(func.count(LGA.id))) or 0
    stations = db.scalar(select(func.count(Station.id))) or 0
    covered_states = db.scalar(
        select(func.count(func.distinct(Station.state_id))).where(Station.state_id.is_not(None))
    ) or 0
    covered_lgas = db.scalar(
        select(func.count(func.distinct(Station.lga_id))).where(Station.lga_id.is_not(None))
    ) or 0
    return {
        "states": states,
        "lgas": lgas,
        "stations": stations,
        "states_with_stations": covered_states,
        "lgas_with_stations": covered_lgas,
    }
