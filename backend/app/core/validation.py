"""Shared validation helpers for the API layer."""

from datetime import date, datetime, timezone
import math

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.core import LGA, Station, State


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def validate_geo(db: Session, state_id: str | None, lga_id: str | None) -> tuple[State | None, LGA | None]:
    """Validate the state/LGA pair, rejecting mismatched or unknown ids."""
    state = None
    lga = None
    if state_id:
        state = db.scalar(select(State).where(State.id == state_id))
        if state is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unknown state")
    if lga_id:
        lga = db.scalar(select(LGA).where(LGA.id == lga_id))
        if lga is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unknown LGA")
        if state is not None and lga.state_id != state.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Selected LGA does not belong to the selected state",
            )
        if state is None:
            state = db.scalar(select(State).where(State.id == lga.state_id))
    return state, lga


def validate_station(db: Session, station_id: str | None) -> Station:
    if not station_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Station is required")
    station = db.scalar(select(Station).where(Station.id == station_id))
    if station is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Station not found")
    return station


def parse_date(value: str | None, default: date | None = None) -> date:
    if not value:
        return default or utcnow().date()
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid date: {value}")


def parse_float(value, field: str, *, minimum: float | None = None, maximum: float | None = None) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"{field} must be a number")
    if not math.isfinite(number):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"{field} must be finite")
    if minimum is not None and number < minimum:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"{field} must be >= {minimum}")
    if maximum is not None and number > maximum:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"{field} must be <= {maximum}")
    return number


def unique_code(db: Session, model, code: str, *, extra_filter=None, message: str = "Code already exists") -> None:
    query = select(model.id).where(func.upper(model.code) == code.upper())
    if extra_filter is not None:
        query = query.where(extra_filter)
    if db.scalar(query):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=message)


def like(value: str | None) -> str | None:
    if not value:
        return None
    return f"%{value.strip()}%"
