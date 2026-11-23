from datetime import datetime
from pydantic import BaseModel, Field


class StationCreate(BaseModel):
    code: str = Field(min_length=1, max_length=40)
    name: str = Field(min_length=2, max_length=180)
    address: str | None = None
    state_id: str | None = None
    lga_id: str | None = None
    city: str | None = None
    gps_lat: str | None = None
    gps_lng: str | None = None
    contact_person: str | None = None
    phone: str | None = None
    email: str | None = None
    status: str = "ACTIVE"


class StationUpdate(BaseModel):
    name: str | None = None
    address: str | None = None
    state_id: str | None = None
    lga_id: str | None = None
    city: str | None = None
    gps_lat: str | None = None
    gps_lng: str | None = None
    contact_person: str | None = None
    phone: str | None = None
    email: str | None = None
    status: str | None = None


class StationOut(BaseModel):
    id: str
    code: str
    name: str
    address: str | None
    city: str | None
    phone: str | None
    status: str
    registered_at: datetime

    model_config = {"from_attributes": True}
