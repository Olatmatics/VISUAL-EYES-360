from datetime import datetime

from pydantic import BaseModel, Field


class StationCreate(BaseModel):
    code: str = Field(min_length=1, max_length=40)
    name: str = Field(min_length=2, max_length=180)
    company_name: str | None = None
    address: str | None = None
    country: str = "Nigeria"
    state_id: str | None = None
    lga_id: str | None = None
    city: str | None = None
    gps_lat: str | None = None
    gps_lng: str | None = None
    manager_name: str | None = None
    manager_phone: str | None = None
    manager_email: str | None = None
    supervisor_name: str | None = None
    supervisor_phone: str | None = None
    supervisor_email: str | None = None
    contact_person: str | None = None
    phone: str | None = None
    email: str | None = None
    notes: str | None = None
    status: str = "ACTIVE"


class StationUpdate(BaseModel):
    name: str | None = None
    company_name: str | None = None
    address: str | None = None
    country: str | None = None
    state_id: str | None = None
    lga_id: str | None = None
    city: str | None = None
    gps_lat: str | None = None
    gps_lng: str | None = None
    manager_name: str | None = None
    manager_phone: str | None = None
    manager_email: str | None = None
    supervisor_name: str | None = None
    supervisor_phone: str | None = None
    supervisor_email: str | None = None
    contact_person: str | None = None
    phone: str | None = None
    email: str | None = None
    notes: str | None = None
    status: str | None = None


class StationOut(BaseModel):
    id: str
    code: str
    name: str
    company_name: str | None = None
    address: str | None
    country: str = "Nigeria"
    state_id: str | None = None
    lga_id: str | None = None
    state_name: str | None = None
    lga_name: str | None = None
    city: str | None
    gps_lat: str | None = None
    gps_lng: str | None = None
    manager_name: str | None = None
    manager_phone: str | None = None
    manager_email: str | None = None
    supervisor_name: str | None = None
    supervisor_phone: str | None = None
    supervisor_email: str | None = None
    contact_person: str | None = None
    phone: str | None
    email: str | None = None
    notes: str | None = None
    status: str
    registered_at: datetime
    dispenser_count: int = 0
    tank_count: int = 0

    model_config = {"from_attributes": True}
