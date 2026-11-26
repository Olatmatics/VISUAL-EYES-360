import uuid
from datetime import datetime, timezone
from sqlalchemy import Boolean, Float, ForeignKey, Integer, String, Text, UniqueConstraint
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
    company_name: Mapped[str | None] = mapped_column(String(180), nullable=True)
    address: Mapped[str | None] = mapped_column(String(255), nullable=True)
    country: Mapped[str] = mapped_column(String(80), default="Nigeria")
    state_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("states.id"), nullable=True, index=True)
    lga_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("lgas.id"), nullable=True, index=True)
    city: Mapped[str | None] = mapped_column(String(120), nullable=True)
    gps_lat: Mapped[str | None] = mapped_column(String(30), nullable=True)
    gps_lng: Mapped[str | None] = mapped_column(String(30), nullable=True)

    # Station management personnel
    manager_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    manager_phone: Mapped[str | None] = mapped_column(String(40), nullable=True)
    manager_email: Mapped[str | None] = mapped_column(String(180), nullable=True)
    supervisor_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    supervisor_phone: Mapped[str | None] = mapped_column(String(40), nullable=True)
    supervisor_email: Mapped[str | None] = mapped_column(String(180), nullable=True)

    contact_person: Mapped[str | None] = mapped_column(String(120), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(40), nullable=True)
    email: Mapped[str | None] = mapped_column(String(180), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    # ACTIVE, INACTIVE, SUSPENDED, MAINTENANCE, PENDING_APPROVAL
    status: Mapped[str] = mapped_column(String(30), default="ACTIVE", index=True)
    registered_at: Mapped[datetime] = mapped_column(default=utcnow)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=utcnow, onupdate=utcnow)

    dispensers: Mapped[list["Dispenser"]] = relationship(back_populates="station")
    tanks: Mapped[list["Tank"]] = relationship(back_populates="station")
    pos_terminals: Mapped[list["POSTerminal"]] = relationship(back_populates="station")

    @property
    def state_name(self) -> str | None:
        return self.state.name if self.state else None

    @property
    def lga_name(self) -> str | None:
        return self.lga.name if self.lga else None

    state: Mapped["State | None"] = relationship(foreign_keys=[state_id])
    lga: Mapped["LGA | None"] = relationship(foreign_keys=[lga_id])


class PumpType(Base):
    """Administrator-managed pump types (not hardcoded)."""
    __tablename__ = "pump_types"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    code: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)


class Dispenser(Base):
    __tablename__ = "dispensers"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    station_id: Mapped[str] = mapped_column(String(36), ForeignKey("stations.id"), index=True)
    code: Mapped[str] = mapped_column(String(40), index=True)
    name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    serial: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    # Wayne, Veeder-Root, Gilbarco, Tatsuno, Tokheim, Bennett, Other
    manufacturer: Mapped[str | None] = mapped_column(String(80), nullable=True, default="Wayne")
    custom_manufacturer: Mapped[str | None] = mapped_column(String(120), nullable=True)
    model: Mapped[str | None] = mapped_column(String(80), nullable=True)
    dispenser_type: Mapped[str | None] = mapped_column(String(60), nullable=True)
    pump_type_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("pump_types.id"), nullable=True)
    # SINGLE, DOUBLE, OTHER
    nozzle_config: Mapped[str] = mapped_column(String(30), default="SINGLE")
    nozzle_count: Mapped[int] = mapped_column(Integer, default=1)
    protocol: Mapped[str | None] = mapped_column(String(80), nullable=True, default="Wayne_Dart")
    interface: Mapped[str | None] = mapped_column(String(40), nullable=True, default="RS485_CurrentLoop")
    status: Mapped[str] = mapped_column(String(30), default="ACTIVE", index=True)
    # ONLINE, OFFLINE, UNKNOWN, FAULT
    communication_status: Mapped[str] = mapped_column(String(30), default="UNKNOWN")
    installation_date: Mapped[datetime | None] = mapped_column(nullable=True)
    fcc_device_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    totalizer_l: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)

    station: Mapped["Station"] = relationship(back_populates="dispensers")
    pump_type: Mapped["PumpType | None"] = relationship()
    nozzles: Mapped[list["Nozzle"]] = relationship(back_populates="dispenser")

    @property
    def display_name(self) -> str:
        return self.name or self.code

    @property
    def brand(self) -> str:
        if self.manufacturer == "Other":
            return self.custom_manufacturer or "Other"
        return self.manufacturer or "Unknown"


class Nozzle(Base):
    __tablename__ = "nozzles"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    dispenser_id: Mapped[str] = mapped_column(String(36), ForeignKey("dispensers.id"), index=True)
    tank_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("tanks.id"), nullable=True, index=True)
    number: Mapped[int] = mapped_column(Integer, default=1)
    name: Mapped[str | None] = mapped_column(String(60), nullable=True)
    product_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("fuel_products.id"), nullable=True)
    price: Mapped[float] = mapped_column(Float, default=0.0)
    status: Mapped[str] = mapped_column(String(30), default="ACTIVE", index=True)
    totalizer_l: Mapped[float] = mapped_column(Float, default=0.0)
    previous_totalizer_l: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)

    dispenser: Mapped["Dispenser"] = relationship(back_populates="nozzles")
    product: Mapped["FuelProduct"] = relationship()
    tank: Mapped["Tank | None"] = relationship()
    fcc: Mapped["FCCDevice"] = relationship(back_populates="nozzle", uselist=False)
    pos: Mapped["POSTerminal"] = relationship(back_populates="nozzle", uselist=False)

    @property
    def label(self) -> str:
        return self.name or f"Nozzle {self.number}"

    @property
    def station_id(self) -> str | None:
        return self.dispenser.station_id if self.dispenser else None


class FCCDevice(Base):
    """FCC Controller (Fuel Control Controller) — user-facing hardware name.

    The underlying microcontroller technology is intentionally not exposed
    in any user-facing field, label or API response.
    """
    __tablename__ = "fcc_devices"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    device_uid: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    api_key_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    serial_number: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    hardware_version: Mapped[str | None] = mapped_column(String(40), nullable=True)
    firmware_version: Mapped[str] = mapped_column(String(40), default="v1.0.0")

    # Assignment hierarchy: station -> dispenser -> nozzle -> POS
    station_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("stations.id"), nullable=True, index=True)
    dispenser_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("dispensers.id"), nullable=True, index=True)
    nozzle_id: Mapped[str] = mapped_column(String(36), ForeignKey("nozzles.id"), unique=True)
    pos_terminal_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("pos_terminals.id"), nullable=True)

    protocol: Mapped[str | None] = mapped_column(String(80), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    mac_address: Mapped[str | None] = mapped_column(String(24), nullable=True)
    sim_info: Mapped[str | None] = mapped_column(String(120), nullable=True)
    connection_mode: Mapped[str] = mapped_column(String(10), default="WIFI")  # WIFI or SIM
    signal_strength_dbm: Mapped[int] = mapped_column(Integer, default=-65)

    calibration_factor: Mapped[float] = mapped_column(Float, default=100.0)  # pulses/litre
    is_online: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    status: Mapped[str] = mapped_column(String(30), default="ACTIVE", index=True)
    installation_date: Mapped[datetime | None] = mapped_column(nullable=True)
    last_heartbeat: Mapped[datetime | None] = mapped_column(nullable=True)
    last_communication_at: Mapped[datetime | None] = mapped_column(nullable=True)

    # Diagnostics (populated by hardware telemetry where supported)
    temperature_c: Mapped[float | None] = mapped_column(Float, nullable=True)
    power_status: Mapped[str | None] = mapped_column(String(30), nullable=True)
    hardware_fault: Mapped[str | None] = mapped_column(String(255), nullable=True)
    communication_errors: Mapped[int] = mapped_column(Integer, default=0)
    firmware_update_status: Mapped[str | None] = mapped_column(String(30), nullable=True)

    created_at: Mapped[datetime] = mapped_column(default=utcnow)

    nozzle: Mapped["Nozzle"] = relationship(back_populates="fcc")
    station: Mapped["Station | None"] = relationship(foreign_keys=[station_id])
    dispenser: Mapped["Dispenser | None"] = relationship(foreign_keys=[dispenser_id])
    pos_terminal: Mapped["POSTerminal | None"] = relationship()


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
    name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    serial_number: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    product_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("fuel_products.id"), nullable=True)
    capacity_l: Mapped[float] = mapped_column(Float, default=50000.0)
    current_volume_l: Mapped[float] = mapped_column(Float, default=32500.0)
    current_level_mm: Mapped[float] = mapped_column(Float, default=1850.0)
    current_water_mm: Mapped[float] = mapped_column(Float, default=12.0)
    current_temperature_c: Mapped[float] = mapped_column(Float, default=27.5)
    hatch_open: Mapped[bool] = mapped_column(Boolean, default=False)

    # Physical configuration
    # UNDERGROUND or SURFACE
    location_type: Mapped[str] = mapped_column(String(30), default="UNDERGROUND")
    position: Mapped[str | None] = mapped_column(String(60), nullable=True)
    dimensions: Mapped[str | None] = mapped_column(String(120), nullable=True)
    installation_date: Mapped[datetime | None] = mapped_column(nullable=True)
    # INSTALLED, PENDING, DECOMMISSIONED
    installation_status: Mapped[str] = mapped_column(String(30), default="INSTALLED")

    # Probe / monitoring device
    probe_id: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    # MODBUS_RS485, CURRENT_LOOP, WIRELESS, OTHER
    probe_comm_type: Mapped[str | None] = mapped_column(String(40), nullable=True)
    monitoring_device: Mapped[str | None] = mapped_column(String(120), nullable=True)

    # Sensor & safety configuration flags
    has_temperature_sensor: Mapped[bool] = mapped_column(Boolean, default=True)
    has_temperature_switch: Mapped[bool] = mapped_column(Boolean, default=False)
    has_tamper_switch: Mapped[bool] = mapped_column(Boolean, default=False)
    has_lid_limit_switch: Mapped[bool] = mapped_column(Boolean, default=False)
    has_high_level_switch: Mapped[bool] = mapped_column(Boolean, default=False)
    has_low_level_switch: Mapped[bool] = mapped_column(Boolean, default=False)
    has_water_detection: Mapped[bool] = mapped_column(Boolean, default=True)

    status: Mapped[str] = mapped_column(String(30), default="ACTIVE", index=True)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)

    station: Mapped["Station"] = relationship(back_populates="tanks")
    product: Mapped["FuelProduct"] = relationship()
    controller: Mapped["TankController"] = relationship(back_populates="tank", uselist=False)
    calibration_rows: Mapped[list["TankCalibration"]] = relationship(back_populates="tank")
    sensors: Mapped[list["TankSensor"]] = relationship(back_populates="tank")

    @property
    def display_name(self) -> str:
        return self.name or self.code

    def volume_from_calibration(self, level_mm: float) -> float | None:
        """Convert measured fuel height to volume using the strapping chart.

        Returns None when no calibration data exists so callers can fall back
        to a clearly-labelled estimate rather than pretending precision.
        """
        rows = sorted(self.calibration_rows, key=lambda r: r.height_mm)
        if not rows:
            return None
        if level_mm <= rows[0].height_mm:
            return rows[0].volume_l
        if level_mm >= rows[-1].height_mm:
            return rows[-1].volume_l
        for lower, upper in zip(rows, rows[1:]):
            if lower.height_mm <= level_mm <= upper.height_mm:
                span = upper.height_mm - lower.height_mm
                if span <= 0:
                    return lower.volume_l
                frac = (level_mm - lower.height_mm) / span
                return lower.volume_l + frac * (upper.volume_l - lower.volume_l)
        return None


class TankCalibration(Base):
    """Strapping / calibration chart rows for a tank."""
    __tablename__ = "tank_calibrations"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    tank_id: Mapped[str] = mapped_column(String(36), ForeignKey("tanks.id"), index=True)
    version: Mapped[str] = mapped_column(String(30), default="v1")
    height_mm: Mapped[float] = mapped_column(Float, index=True)
    volume_l: Mapped[float] = mapped_column(Float)
    water_mm: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)

    tank: Mapped["Tank"] = relationship(back_populates="calibration_rows")


class TankSensor(Base):
    """Per-sensor configuration and health for a tank."""
    __tablename__ = "tank_sensors"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    tank_id: Mapped[str] = mapped_column(String(36), ForeignKey("tanks.id"), index=True)
    # TEMPERATURE_SENSOR, TEMPERATURE_SWITCH, TAMPER_SWITCH, LID_LIMIT_SWITCH,
    # HIGH_LEVEL_SWITCH, LOW_LEVEL_SWITCH, WATER_DETECTION, PROBE, OTHER
    sensor_type: Mapped[str] = mapped_column(String(50), index=True)
    label: Mapped[str | None] = mapped_column(String(120), nullable=True)
    is_installed: Mapped[bool] = mapped_column(Boolean, default=True)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    # OK, FAULT, OFFLINE, UNKNOWN
    status: Mapped[str] = mapped_column(String(30), default="OK")
    last_reading_at: Mapped[datetime | None] = mapped_column(nullable=True)
    notes: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)

    tank: Mapped["Tank"] = relationship(back_populates="sensors")


class TankController(Base):
    __tablename__ = "tank_controllers"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    device_uid: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    api_key_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    tank_id: Mapped[str] = mapped_column(String(36), ForeignKey("tanks.id"), unique=True)
    firmware_version: Mapped[str] = mapped_column(String(20), default="v1.0.0")
    connection_mode: Mapped[str] = mapped_column(String(10), default="WIFI")
    signal_strength_dbm: Mapped[int] = mapped_column(Integer, default=-68)
    modbus_address: Mapped[int] = mapped_column(Integer, default=1)
    is_online: Mapped[bool] = mapped_column(Boolean, default=False)
    last_heartbeat: Mapped[datetime | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)

    tank: Mapped["Tank"] = relationship(back_populates="controller")


class TankReading(Base):
    __tablename__ = "tank_readings"
    # Partition key is part of the PK so PostgreSQL can create monthly
    # partitions. SQLite ignores this dialect option and keeps its own schema.
    __table_args__ = {"postgresql_partition_by": "RANGE (recorded_at)"}
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    tank_id: Mapped[str] = mapped_column(String(36), ForeignKey("tanks.id"), index=True)
    fuel_level_mm: Mapped[float] = mapped_column(Float)
    fuel_volume_l: Mapped[float] = mapped_column(Float)
    water_level_mm: Mapped[float] = mapped_column(Float, default=0.0)
    temperature_c: Mapped[float] = mapped_column(Float, default=25.0)
    ullage_l: Mapped[float] = mapped_column(Float, default=0.0)
    hatch_open: Mapped[bool] = mapped_column(Boolean, default=False)
    volume_source: Mapped[str] = mapped_column(String(30), default="DEVICE_REPORTED")
    recorded_at: Mapped[datetime] = mapped_column(default=utcnow, index=True, primary_key=True)


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
    ledger_entries: Mapped[list["WalletLedgerEntry"]] = relationship(back_populates="wallet")


class WalletLedgerEntry(Base):
    """Immutable-style wallet balance audit ledger."""
    __tablename__ = "wallet_ledger_entries"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    wallet_id: Mapped[str] = mapped_column(String(36), ForeignKey("wallets.id"), index=True)
    reference: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    entry_type: Mapped[str] = mapped_column(String(30), index=True)  # FUNDING, ADJUSTMENT, SALE_DEBIT, REFUND
    amount: Mapped[float] = mapped_column(Float)
    balance_before: Mapped[float] = mapped_column(Float)
    balance_after: Mapped[float] = mapped_column(Float)
    payment_reference: Mapped[str | None] = mapped_column(String(80), nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(80), nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=utcnow, index=True)

    wallet: Mapped["Wallet"] = relationship(back_populates="ledger_entries")


class RFIDCard(Base):
    __tablename__ = "rfid_cards"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    card_uid: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    customer_id: Mapped[str] = mapped_column(String(36), ForeignKey("customers.id"), index=True)
    # Cards are nationwide. This records where the manager first registered it,
    # it never restricts where the card can be used.
    home_station_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("stations.id"), nullable=True, index=True
    )
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
    status: Mapped[str] = mapped_column(String(30), default="INITIATED")  # INITIATED, VERIFIED, FAILED, REFUNDED
    authorized_at: Mapped[datetime | None] = mapped_column(nullable=True)
    purpose: Mapped[str] = mapped_column(String(30), default="FUEL", index=True)  # FUEL, WALLET_FUNDING
    customer_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("customers.id"), nullable=True, index=True)
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
    alert_ref: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    station_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("stations.id"), nullable=True, index=True)
    # TANK_SECURITY, FUEL_DISCREPANCY, DISPENSER, FCC_CONTROLLER, SYSTEM
    category: Mapped[str] = mapped_column(String(40), default="SYSTEM", index=True)
    alert_type: Mapped[str] = mapped_column(String(60), index=True)
    # CRITICAL, HIGH, MEDIUM, LOW, INFO
    severity: Mapped[str] = mapped_column(String(20), default="INFO", index=True)
    title: Mapped[str] = mapped_column(String(180))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Geo denormalisation for nationwide filtering
    state_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    lga_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)

    device_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    device_id: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    entity_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    entity_id: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Readings / threshold context
    expected_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    actual_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    discrepancy: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Workflow
    # NEW, ACKNOWLEDGED, INVESTIGATING, RESOLVED, ESCALATED
    status: Mapped[str] = mapped_column(String(30), default="NEW", index=True)
    is_resolved: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    acknowledged_at: Mapped[datetime | None] = mapped_column(nullable=True)
    acknowledged_by: Mapped[str | None] = mapped_column(String(80), nullable=True)
    assigned_to: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    resolution_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    resolved_by: Mapped[str | None] = mapped_column(String(80), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(nullable=True)
    escalated: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[datetime] = mapped_column(default=utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(default=utcnow, onupdate=utcnow)

    station: Mapped["Station | None"] = relationship()


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


class TankDelivery(Base):
    """Fuel delivery registration and verification."""
    __tablename__ = "tank_deliveries"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    reference: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    station_id: Mapped[str] = mapped_column(String(36), ForeignKey("stations.id"), index=True)
    tank_id: Mapped[str] = mapped_column(String(36), ForeignKey("tanks.id"), index=True)
    product_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("fuel_products.id"), nullable=True)
    supplier: Mapped[str | None] = mapped_column(String(180), nullable=True)
    vehicle_plate: Mapped[str | None] = mapped_column(String(40), nullable=True)
    tanker_serial: Mapped[str | None] = mapped_column(String(80), nullable=True)
    delivered_quantity_l: Mapped[float] = mapped_column(Float, default=0.0)
    received_quantity_l: Mapped[float] = mapped_column(Float, default=0.0)
    variance_l: Mapped[float] = mapped_column(Float, default=0.0)
    # PENDING, VERIFIED, DISPUTED, REJECTED
    status: Mapped[str] = mapped_column(String(30), default="PENDING", index=True)
    delivery_date: Mapped[datetime] = mapped_column(default=utcnow, index=True)
    verified_by: Mapped[str | None] = mapped_column(String(80), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)

    station: Mapped["Station"] = relationship()
    tank: Mapped["Tank"] = relationship()


class MaintenanceRecord(Base):
    """Preventive and corrective maintenance tracking."""
    __tablename__ = "maintenance_records"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    reference: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    station_id: Mapped[str] = mapped_column(String(36), ForeignKey("stations.id"), index=True)
    # DISPENSER, TANK, FCC_CONTROLLER, POS_TERMINAL, PROBE, SENSOR, OTHER
    device_type: Mapped[str] = mapped_column(String(40), index=True)
    device_id: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    # PREVENTIVE, CORRECTIVE, EMERGENCY
    maintenance_type: Mapped[str] = mapped_column(String(30), default="PREVENTIVE")
    title: Mapped[str] = mapped_column(String(180))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    # OPEN, IN_PROGRESS, COMPLETED, CANCELLED
    status: Mapped[str] = mapped_column(String(30), default="OPEN", index=True)
    priority: Mapped[str] = mapped_column(String(20), default="MEDIUM")
    assigned_to: Mapped[str | None] = mapped_column(String(80), nullable=True)
    scheduled_at: Mapped[datetime | None] = mapped_column(nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(nullable=True)
    downtime_hours: Mapped[float] = mapped_column(Float, default=0.0)
    cost: Mapped[float] = mapped_column(Float, default=0.0)
    created_by: Mapped[str | None] = mapped_column(String(80), nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=utcnow, onupdate=utcnow)

    station: Mapped["Station"] = relationship()


class PumpReconciliation(Base):
    """Nozzle-level reconciliation across POS, FCC, CPU totalizer and pulser."""
    __tablename__ = "pump_reconciliations"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    station_id: Mapped[str] = mapped_column(String(36), ForeignKey("stations.id"), index=True)
    dispenser_id: Mapped[str] = mapped_column(String(36), ForeignKey("dispensers.id"), index=True)
    nozzle_id: Mapped[str] = mapped_column(String(36), ForeignKey("nozzles.id"), index=True)
    shift_date: Mapped[str] = mapped_column(String(20), index=True)

    product_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    pos_volume_l: Mapped[float] = mapped_column(Float, default=0.0)
    fcc_volume_l: Mapped[float] = mapped_column(Float, default=0.0)
    previous_totalizer_l: Mapped[float] = mapped_column(Float, default=0.0)
    current_totalizer_l: Mapped[float] = mapped_column(Float, default=0.0)
    cpu_volume_l: Mapped[float] = mapped_column(Float, default=0.0)
    pulser_volume_l: Mapped[float] = mapped_column(Float, default=0.0)

    calculated_volume_l: Mapped[float] = mapped_column(Float, default=0.0)
    expected_volume_l: Mapped[float] = mapped_column(Float, default=0.0)
    actual_volume_l: Mapped[float] = mapped_column(Float, default=0.0)
    variance_l: Mapped[float] = mapped_column(Float, default=0.0)
    variance_percentage: Mapped[float] = mapped_column(Float, default=0.0)

    # NORMAL, WARNING, CRITICAL_INVESTIGATION
    status: Mapped[str] = mapped_column(String(40), default="NORMAL", index=True)
    investigation_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    recorded_at: Mapped[datetime] = mapped_column(default=utcnow)

    station: Mapped["Station"] = relationship()
    dispenser: Mapped["Dispenser"] = relationship()
    nozzle: Mapped["Nozzle"] = relationship()


class DeviceEvent(Base):
    """Deduplicated accepted device-event log and telemetry audit trail."""
    __tablename__ = "device_events"
    __table_args__ = (
        UniqueConstraint("event_key", "received_at"),
        {"postgresql_partition_by": "RANGE (received_at)"},
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    device_uid: Mapped[str] = mapped_column(String(64), index=True)
    device_type: Mapped[str] = mapped_column(String(40), index=True)  # FCC_CONTROLLER, TANK_CONTROLLER
    event_key: Mapped[str | None] = mapped_column(String(160), index=True, nullable=True)
    station_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    event_type: Mapped[str] = mapped_column(String(60), index=True)
    payload_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    # ACCEPTED, DUPLICATE, QUARANTINED, REJECTED, STALE
    processing_status: Mapped[str] = mapped_column(String(30), default="ACCEPTED", index=True)
    device_timestamp: Mapped[datetime | None] = mapped_column(nullable=True)
    received_at: Mapped[datetime] = mapped_column(default=utcnow, index=True, primary_key=True)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)


class DeviceCommand(Base):
    """Outbound command queued for a field controller (prototype transport)."""
    __tablename__ = "device_commands"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    device_uid: Mapped[str] = mapped_column(String(64), index=True)
    command_type: Mapped[str] = mapped_column(String(40), index=True)
    payload_json: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="PENDING", index=True)
    created_at: Mapped[datetime] = mapped_column(default=utcnow, index=True)
    ack_at: Mapped[datetime | None] = mapped_column(nullable=True)


class HardwareExchange(Base):
    """Bench-visible record of JSON exchanged between ESP32 boards and backend."""
    __tablename__ = "hardware_exchanges"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    # IN = hardware -> software, OUT = software -> hardware.
    direction: Mapped[str] = mapped_column(String(10), index=True)
    device_uid: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    endpoint: Mapped[str] = mapped_column(String(180), index=True)
    method: Mapped[str] = mapped_column(String(10), default="POST")
    status_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    request_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    response_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=utcnow, index=True)


class SystemSetting(Base):
    """Persisted operator configuration (telemetry and network parameters)."""
    __tablename__ = "system_settings"
    key: Mapped[str] = mapped_column(String(80), primary_key=True)
    value: Mapped[str] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(default=utcnow, onupdate=utcnow)
    updated_by: Mapped[str | None] = mapped_column(String(80), nullable=True)


class Notification(Base):
    """Outbound notification queue (email + in-app)."""
    __tablename__ = "notifications"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    alert_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("system_alerts.id"), nullable=True, index=True)
    channel: Mapped[str] = mapped_column(String(20), default="EMAIL")  # EMAIL, IN_APP
    recipient: Mapped[str] = mapped_column(String(180), index=True)
    subject: Mapped[str] = mapped_column(String(255))
    body: Mapped[str] = mapped_column(Text)
    # PENDING, SENT, FAILED, SKIPPED
    status: Mapped[str] = mapped_column(String(20), default="PENDING", index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    dedupe_key: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    sent_at: Mapped[datetime | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=utcnow, index=True)

    alert: Mapped["SystemAlert | None"] = relationship()
