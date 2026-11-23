import uuid
from datetime import datetime, timezone
from sqlalchemy import Boolean, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base


def new_id() -> str:
    return str(uuid.uuid4())


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class State(Base):
    __tablename__ = "states"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    code: Mapped[str | None] = mapped_column(String(10), nullable=True)
    lgas: Mapped[list["LGA"]] = relationship(back_populates="state")


class LGA(Base):
    __tablename__ = "lgas"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    state_id: Mapped[str] = mapped_column(String(36), ForeignKey("states.id"), index=True)
    name: Mapped[str] = mapped_column(String(120), index=True)
    state: Mapped["State"] = relationship(back_populates="lgas")


class FuelProduct(Base):
    __tablename__ = "fuel_products"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    code: Mapped[str] = mapped_column(String(10), unique=True)
    name: Mapped[str] = mapped_column(String(120))


class Station(Base):
    __tablename__ = "stations"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    code: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(180))
    address: Mapped[str | None] = mapped_column(String(255), nullable=True)
    state_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("states.id"), nullable=True)
    lga_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("lgas.id"), nullable=True)
    city: Mapped[str | None] = mapped_column(String(120), nullable=True)
    gps_lat: Mapped[str | None] = mapped_column(String(30), nullable=True)
    gps_lng: Mapped[str | None] = mapped_column(String(30), nullable=True)
    contact_person: Mapped[str | None] = mapped_column(String(120), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(40), nullable=True)
    email: Mapped[str | None] = mapped_column(String(180), nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="ACTIVE")
    registered_at: Mapped[datetime] = mapped_column(default=utcnow)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=utcnow, onupdate=utcnow)

    dispensers: Mapped[list["Dispenser"]] = relationship(back_populates="station")
    tanks: Mapped[list["Tank"]] = relationship(back_populates="station")
    pos_terminals: Mapped[list["POSTerminal"]] = relationship(back_populates="station")


class Dispenser(Base):
    __tablename__ = "dispensers"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    station_id: Mapped[str] = mapped_column(String(36), ForeignKey("stations.id"), index=True)
    code: Mapped[str] = mapped_column(String(40), index=True)
    manufacturer: Mapped[str | None] = mapped_column(String(80), nullable=True, default="Wayne")
    model: Mapped[str | None] = mapped_column(String(80), nullable=True)
    protocol: Mapped[str | None] = mapped_column(String(80), nullable=True, default="Wayne_Dart")
    interface: Mapped[str | None] = mapped_column(String(40), nullable=True, default="RS485_CurrentLoop")
    serial: Mapped[str | None] = mapped_column(String(80), nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="ACTIVE")
    totalizer_l: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)

    station: Mapped["Station"] = relationship(back_populates="dispensers")
    nozzles: Mapped[list["Nozzle"]] = relationship(back_populates="dispenser")


class Nozzle(Base):
    __tablename__ = "nozzles"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    dispenser_id: Mapped[str] = mapped_column(String(36), ForeignKey("dispensers.id"), index=True)
    tank_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("tanks.id"), nullable=True)
    number: Mapped[int] = mapped_column(Integer, default=1)
    product_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("fuel_products.id"), nullable=True)
    price: Mapped[float] = mapped_column(Float, default=0.0)
    status: Mapped[str] = mapped_column(String(30), default="ACTIVE")
    totalizer_l: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)

    dispenser: Mapped["Dispenser"] = relationship(back_populates="nozzles")
    product: Mapped["FuelProduct"] = relationship()
    fcc: Mapped["FCCDevice"] = relationship(back_populates="nozzle", uselist=False)
    pos: Mapped["POSTerminal"] = relationship(back_populates="nozzle", uselist=False)


class FCCDevice(Base):
    __tablename__ = "fcc_devices"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    device_uid: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    nozzle_id: Mapped[str] = mapped_column(String(36), ForeignKey("nozzles.id"), unique=True)
    firmware_version: Mapped[str] = mapped_column(String(20), default="v1.0.4-esp32s3")
    connection_mode: Mapped[str] = mapped_column(String(10), default="WIFI")  # WIFI or SIM
    signal_strength_dbm: Mapped[int] = mapped_column(Integer, default=-65)
    calibration_factor: Mapped[float] = mapped_column(Float, default=100.0)  # pulses/litre
    is_online: Mapped[bool] = mapped_column(Boolean, default=True)
    last_heartbeat: Mapped[datetime | None] = mapped_column(default=utcnow)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)

    nozzle: Mapped["Nozzle"] = relationship(back_populates="fcc")


class POSTerminal(Base):
    __tablename__ = "pos_terminals"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    terminal_id: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    serial_number: Mapped[str] = mapped_column(String(50), unique=True)
    provider: Mapped[str] = mapped_column(String(30), default="OPAY")
    station_id: Mapped[str] = mapped_column(String(36), ForeignKey("stations.id"))
    nozzle_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("nozzles.id"), unique=True, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)

    station: Mapped["Station"] = relationship(back_populates="pos_terminals")
    nozzle: Mapped["Nozzle"] = relationship(back_populates="pos")


class Tank(Base):
    __tablename__ = "tanks"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    station_id: Mapped[str] = mapped_column(String(36), ForeignKey("stations.id"), index=True)
    code: Mapped[str] = mapped_column(String(40), index=True)
    product_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("fuel_products.id"), nullable=True)
    capacity_l: Mapped[float] = mapped_column(Float, default=50000.0)
    current_volume_l: Mapped[float] = mapped_column(Float, default=32500.0)
    current_level_mm: Mapped[float] = mapped_column(Float, default=1850.0)
    current_water_mm: Mapped[float] = mapped_column(Float, default=12.0)
    current_temperature_c: Mapped[float] = mapped_column(Float, default=27.5)
    hatch_open: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(30), default="ACTIVE")
    created_at: Mapped[datetime] = mapped_column(default=utcnow)

    station: Mapped["Station"] = relationship(back_populates="tanks")
    product: Mapped["FuelProduct"] = relationship()
    controller: Mapped["TankController"] = relationship(back_populates="tank", uselist=False)


class TankController(Base):
    __tablename__ = "tank_controllers"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    device_uid: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    tank_id: Mapped[str] = mapped_column(String(36), ForeignKey("tanks.id"), unique=True)
    firmware_version: Mapped[str] = mapped_column(String(20), default="v1.0.2-tank-esp32")
    connection_mode: Mapped[str] = mapped_column(String(10), default="WIFI")
    signal_strength_dbm: Mapped[int] = mapped_column(Integer, default=-68)
    modbus_address: Mapped[int] = mapped_column(Integer, default=1)
    is_online: Mapped[bool] = mapped_column(Boolean, default=True)
    last_heartbeat: Mapped[datetime | None] = mapped_column(default=utcnow)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)

    tank: Mapped["Tank"] = relationship(back_populates="controller")


class TankReading(Base):
    __tablename__ = "tank_readings"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    tank_id: Mapped[str] = mapped_column(String(36), ForeignKey("tanks.id"), index=True)
    fuel_level_mm: Mapped[float] = mapped_column(Float)
    fuel_volume_l: Mapped[float] = mapped_column(Float)
    water_level_mm: Mapped[float] = mapped_column(Float, default=0.0)
    temperature_c: Mapped[float] = mapped_column(Float, default=25.0)
    ullage_l: Mapped[float] = mapped_column(Float, default=0.0)
    hatch_open: Mapped[bool] = mapped_column(Boolean, default=False)
    recorded_at: Mapped[datetime] = mapped_column(default=utcnow, index=True)


class Customer(Base):
    __tablename__ = "customers"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    full_name: Mapped[str] = mapped_column(String(180))
    phone: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    email: Mapped[str | None] = mapped_column(String(180), nullable=True)
    category: Mapped[str] = mapped_column(String(40), default="SPECIAL_CUSTOMER")  # CORPORATE, VIP, FLEET
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)

    wallet: Mapped["Wallet"] = relationship(back_populates="customer", uselist=False)
    cards: Mapped[list["RFIDCard"]] = relationship(back_populates="customer")


class Wallet(Base):
    __tablename__ = "wallets"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    customer_id: Mapped[str] = mapped_column(String(36), ForeignKey("customers.id"), unique=True)
    balance: Mapped[float] = mapped_column(Float, default=0.0)
    reserved_balance: Mapped[float] = mapped_column(Float, default=0.0)
    updated_at: Mapped[datetime] = mapped_column(default=utcnow, onupdate=utcnow)

    customer: Mapped["Customer"] = relationship(back_populates="wallet")


class RFIDCard(Base):
    __tablename__ = "rfid_cards"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    card_uid: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    customer_id: Mapped[str] = mapped_column(String(36), ForeignKey("customers.id"), index=True)
    auth_key_hash: Mapped[str] = mapped_column(String(128))
    is_blocked: Mapped[bool] = mapped_column(Boolean, default=False)
    daily_spend_limit: Mapped[float] = mapped_column(Float, default=100000.0)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)

    customer: Mapped["Customer"] = relationship(back_populates="cards")


class Fleet(Base):
    __tablename__ = "fleets"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(180))
    code: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    organization: Mapped[str] = mapped_column(String(180))
    spending_limit: Mapped[float] = mapped_column(Float, default=1000000.0)
    status: Mapped[str] = mapped_column(String(30), default="ACTIVE")
    created_at: Mapped[datetime] = mapped_column(default=utcnow)

    vehicles: Mapped[list["Vehicle"]] = relationship(back_populates="fleet")


class Vehicle(Base):
    __tablename__ = "vehicles"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    fleet_id: Mapped[str] = mapped_column(String(36), ForeignKey("fleets.id"), index=True)
    plate_number: Mapped[str] = mapped_column(String(30), unique=True, index=True)
    vehicle_type: Mapped[str] = mapped_column(String(60))  # TRUCK, BUS, SEDAN, VAN
    driver_name: Mapped[str] = mapped_column(String(120))
    fuel_type: Mapped[str] = mapped_column(String(20), default="PMS")
    spending_limit: Mapped[float] = mapped_column(Float, default=50000.0)
    odometer_km: Mapped[float] = mapped_column(Float, default=0.0)
    status: Mapped[str] = mapped_column(String(30), default="ACTIVE")
    created_at: Mapped[datetime] = mapped_column(default=utcnow)

    fleet: Mapped["Fleet"] = relationship(back_populates="vehicles")


class FuelTransaction(Base):
    __tablename__ = "fuel_transactions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    transaction_ref: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    station_id: Mapped[str] = mapped_column(String(36), ForeignKey("stations.id"), index=True)
    dispenser_id: Mapped[str] = mapped_column(String(36), ForeignKey("dispensers.id"), index=True)
    nozzle_id: Mapped[str] = mapped_column(String(36), ForeignKey("nozzles.id"), index=True)
    fcc_device_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    customer_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("customers.id"), nullable=True)
    payment_channel: Mapped[str] = mapped_column(String(30))  # OPAY_POS, BANK_TRANSFER, RFID_WALLET, CASH
    payment_ref: Mapped[str | None] = mapped_column(String(80), nullable=True)
    unit_price: Mapped[float] = mapped_column(Float)
    requested_amount: Mapped[float] = mapped_column(Float)
    requested_volume: Mapped[float] = mapped_column(Float)

    # Dual measurement verification
    dispenser_cpu_volume: Mapped[float] = mapped_column(Float, default=0.0)
    independent_pulser_volume: Mapped[float] = mapped_column(Float, default=0.0)
    raw_pulse_count: Mapped[int] = mapped_column(Integer, default=0)
    volume_difference: Mapped[float] = mapped_column(Float, default=0.0)
    discrepancy_alert: Mapped[bool] = mapped_column(Boolean, default=False)
    investigation_status: Mapped[str] = mapped_column(String(40), default="NORMAL")  # NORMAL, UNDER_REVIEW, RESOLVED, CONFIRMED_INCIDENT
    investigation_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    total_amount_billed: Mapped[float] = mapped_column(Float, default=0.0)
    status: Mapped[str] = mapped_column(String(30), default="COMPLETED")  # PENDING, DISPENSING, COMPLETED, INTERRUPTED
    started_at: Mapped[datetime] = mapped_column(default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(default=utcnow)

    station: Mapped["Station"] = relationship()
    dispenser: Mapped["Dispenser"] = relationship()
    nozzle: Mapped["Nozzle"] = relationship()
    customer: Mapped["Customer"] = relationship()


class PaymentRecord(Base):
    __tablename__ = "payment_records"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    transaction_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    reference: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    amount: Mapped[float] = mapped_column(Float)
    currency: Mapped[str] = mapped_column(String(10), default="NGN")
    provider: Mapped[str] = mapped_column(String(40), default="OPAY")
    payment_method: Mapped[str] = mapped_column(String(40), default="CARD_POS")  # CARD_POS, BANK_TRANSFER, WALLET
    status: Mapped[str] = mapped_column(String(30), default="VERIFIED")  # INITIATED, VERIFIED, FAILED, REFUNDED
    pos_terminal_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    station_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    nozzle_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)


class TankReconciliation(Base):
    __tablename__ = "tank_reconciliations"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    tank_id: Mapped[str] = mapped_column(String(36), ForeignKey("tanks.id"), index=True)
    station_id: Mapped[str] = mapped_column(String(36), ForeignKey("stations.id"), index=True)
    shift_date: Mapped[str] = mapped_column(String(20), index=True)
    opening_stock_l: Mapped[float] = mapped_column(Float)
    deliveries_l: Mapped[float] = mapped_column(Float, default=0.0)
    sales_cpu_l: Mapped[float] = mapped_column(Float)
    sales_pulser_l: Mapped[float] = mapped_column(Float)
    expected_closing_stock_l: Mapped[float] = mapped_column(Float)
    actual_atg_closing_stock_l: Mapped[float] = mapped_column(Float)
    variance_l: Mapped[float] = mapped_column(Float)
    variance_percentage: Mapped[float] = mapped_column(Float, default=0.0)
    status: Mapped[str] = mapped_column(String(40), default="NORMAL")  # NORMAL, WARNING, CRITICAL_INVESTIGATION
    investigation_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    recorded_at: Mapped[datetime] = mapped_column(default=utcnow)

    tank: Mapped["Tank"] = relationship()
    station: Mapped["Station"] = relationship()


class SystemAlert(Base):
    __tablename__ = "system_alerts"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    station_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("stations.id"), nullable=True)
    alert_type: Mapped[str] = mapped_column(String(60), index=True)  # PULSER_DISCREPANCY, TANK_HATCH_OPEN, LOW_FUEL, WATER_DETECTED, FCC_OFFLINE
    severity: Mapped[str] = mapped_column(String(20), default="INFO")  # INFO, WARNING, CRITICAL
    title: Mapped[str] = mapped_column(String(180))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    entity_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    entity_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    is_resolved: Mapped[bool] = mapped_column(Boolean, default=False)
    resolved_by: Mapped[str | None] = mapped_column(String(80), nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=utcnow, index=True)
    resolved_at: Mapped[datetime | None] = mapped_column(nullable=True)

    station: Mapped["Station"] = relationship()


class PriceHistory(Base):
    __tablename__ = "price_history"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    station_id: Mapped[str] = mapped_column(String(36), ForeignKey("stations.id"), index=True)
    dispenser_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    nozzle_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    product_code: Mapped[str] = mapped_column(String(20))
    previous_price: Mapped[float] = mapped_column(Float)
    new_price: Mapped[float] = mapped_column(Float)
    changed_by_user_id: Mapped[str] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(30), default="CONFIRMED")  # CONFIRMED, PENDING, FAILED
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
