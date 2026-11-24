"""
VISUAL EYES 360 — Complete Production Seed Script
Seeds stations, dual-hose Wayne dispensers, dedicated FCC Controllers,
ATG tanks, POS terminals, transactions with dual pulser verification,
special customer RFID wallets, and security alerts.
"""

from datetime import datetime, timedelta, timezone
from sqlalchemy import select
from app.core.security import hash_password
from app.db.base import SessionLocal
from app.db.init_db import init_db
from app.models.auth import Permission, Role, User, UserPermission
from app.models.core import (
    Customer,
    Dispenser,
    FCCDevice,
    Fleet,
    FuelProduct,
    FuelTransaction,
    LGA,
    Nozzle,
    PaymentRecord,
    POSTerminal,
    PriceHistory,
    RFIDCard,
    State,
    Station,
    SystemAlert,
    Tank,
    TankController,
    TankReconciliation,
    Vehicle,
    Wallet,
)


def seed():
    print("Initializing database tables and catalogues...")
    init_db()

    with SessionLocal() as db:
        admin_role = db.scalar(select(Role).where(Role.code == "SUPERIOR_ADMIN"))
        manager_role = db.scalar(select(Role).where(Role.code == "MANAGER"))

        # 1. Superior Administrator
        super_admin = db.scalar(select(User).where(User.user_id == "SUPERADMIN001"))
        if not super_admin:
            print("Creating Superior Administrator (SUPERADMIN001)...")
            super_admin = User(
                user_id="SUPERADMIN001",
                full_name="Chief Executive Director",
                role_id=admin_role.id,
                phone="+2348030000001",
                email="admin@visualeyes360.ng",
                password_hash=hash_password("Admin@1234"),
                is_super_admin=True,
                is_active=True,
                all_stations=True,
                must_change_password=False,
            )
            db.add(super_admin)
            db.flush()

        # 2. Fuel Products
        pms = db.scalar(select(FuelProduct).where(FuelProduct.code == "PMS"))
        ago = db.scalar(select(FuelProduct).where(FuelProduct.code == "AGO"))
        dpk = db.scalar(select(FuelProduct).where(FuelProduct.code == "DPK"))

        # 3. Stations in Nigeria
        fct_state = db.scalar(select(State).where(State.name == "FCT Abuja"))
        fct_lga = db.scalar(select(LGA).where(LGA.name == "Abuja Municipal")) if fct_state else None
        lag_state = db.scalar(select(State).where(State.name == "Lagos"))
        lag_lga = db.scalar(select(LGA).where(LGA.name == "Eti-Osa")) if lag_state else None

        # Station 1: Abuja Central Mega Station
        st_abj = db.scalar(select(Station).where(Station.code == "ABJ-001"))
        if not st_abj:
            print("Creating Station 1: Central Mega Station Abuja (ABJ-001)...")
            st_abj = Station(
                code="ABJ-001",
                name="Central Mega Station Abuja",
                address="Plot 104, Herbert Macaulay Way, Central Business District",
                city="Abuja",
                state_id=fct_state.id if fct_state else None,
                lga_id=fct_lga.id if fct_lga else None,
                phone="+2348020000002",
                email="station.abj@visualeyes360.ng",
                contact_person="Engr. Aliyu Mohammed",
                status="ACTIVE",
            )
            db.add(st_abj)
            db.flush()

            # Tanks for Abuja Station
            tank_pms_abj = Tank(
                station_id=st_abj.id,
                code="TANK-ABJ-01-PMS",
                product_id=pms.id if pms else None,
                capacity_l=50000.0,
                current_volume_l=34250.0,
                current_level_mm=1950.0,
                current_water_mm=8.5,
                current_temperature_c=28.0,
                status="ACTIVE",
            )
            tank_ago_abj = Tank(
                station_id=st_abj.id,
                code="TANK-ABJ-02-AGO",
                product_id=ago.id if ago else None,
                capacity_l=50000.0,
                current_volume_l=21800.0,
                current_level_mm=1320.0,
                current_water_mm=11.2,
                current_temperature_c=27.5,
                status="ACTIVE",
            )
            db.add_all([tank_pms_abj, tank_ago_abj])
            db.flush()

            # Dedicated FCC Tank Controllers (1 per tank)
            db.add(TankController(
                device_uid="TC-FCC-ABJ-T1",
                tank_id=tank_pms_abj.id,
                connection_mode="WIFI",
                signal_strength_dbm=-64,
                modbus_address=1,
                is_online=True,
            ))
            db.add(TankController(
                device_uid="TC-FCC-ABJ-T2",
                tank_id=tank_ago_abj.id,
                connection_mode="SIM",
                signal_strength_dbm=-71,
                modbus_address=2,
                is_online=True,
            ))

            # Dispenser 1: Wayne iGEM Dual-Nozzle
            disp1 = Dispenser(
                station_id=st_abj.id,
                code="DISP-01",
                manufacturer="Wayne",
                model="iGEM 2-Hose",
                protocol="Wayne_Dart",
                interface="RS485_CurrentLoop",
                serial="WN-2026-9901A",
                status="ACTIVE",
                totalizer_l=145200.0,
            )
            db.add(disp1)
            db.flush()

            # Nozzle 1 (PMS) & Nozzle 2 (AGO)
            nozzle1 = Nozzle(
                dispenser_id=disp1.id,
                tank_id=tank_pms_abj.id,
                number=1,
                product_id=pms.id if pms else None,
                price=850.00,
                status="ACTIVE",
                totalizer_l=82400.0,
            )
            nozzle2 = Nozzle(
                dispenser_id=disp1.id,
                tank_id=tank_ago_abj.id,
                number=2,
                product_id=ago.id if ago else None,
                price=1150.00,
                status="ACTIVE",
                totalizer_l=62800.0,
            )
            db.add_all([nozzle1, nozzle2])
            db.flush()

            # ONE Dedicated FCC Controller PER NOZZLE
            db.add(FCCDevice(
                device_uid="FCC-S3-ABJ-D1-N1",
                nozzle_id=nozzle1.id,
                firmware_version="v1.0.4-fcc",
                connection_mode="WIFI",
                signal_strength_dbm=-62,
                calibration_factor=100.0,
                is_online=True,
            ))
            db.add(FCCDevice(
                device_uid="FCC-S3-ABJ-D1-N2",
                nozzle_id=nozzle2.id,
                firmware_version="v1.0.4-fcc",
                connection_mode="SIM",
                signal_strength_dbm=-69,
                calibration_factor=100.0,
                is_online=True,
            ))

            # Dedicated Assigned OPay SmartPOS Terminals
            db.add(POSTerminal(
                terminal_id="OPAY-POS-ABJ-N1",
                serial_number="OPAY-SN-882101",
                provider="OPAY",
                station_id=st_abj.id,
                nozzle_id=nozzle1.id,
                is_active=True,
            ))
            db.add(POSTerminal(
                terminal_id="OPAY-POS-ABJ-N2",
                serial_number="OPAY-SN-882102",
                provider="OPAY",
                station_id=st_abj.id,
                nozzle_id=nozzle2.id,
                is_active=True,
            ))

        # Station 2: Victoria Island Express Station (Lagos)
        st_lag = db.scalar(select(Station).where(Station.code == "LAG-001"))
        if not st_lag:
            print("Creating Station 2: Victoria Island Express Station (LAG-001)...")
            st_lag = Station(
                code="LAG-001",
                name="Victoria Island Express Station",
                address="Ahmadu Bello Way, Victoria Island",
                city="Lagos",
                state_id=lag_state.id if lag_state else None,
                lga_id=lag_lga.id if lag_lga else None,
                phone="+2348033333333",
                email="station.lag@visualeyes360.ng",
                contact_person="Chinedu Okonkwo",
                status="ACTIVE",
            )
            db.add(st_lag)
            db.flush()

            tank_pms_lag = Tank(
                station_id=st_lag.id,
                code="TANK-LAG-01-PMS",
                product_id=pms.id if pms else None,
                capacity_l=50000.0,
                current_volume_l=18400.0,
                current_level_mm=1120.0,
                current_water_mm=28.4,  # Triggers water alert
                current_temperature_c=29.5,
                hatch_open=True,  # Triggers security alert
                status="ACTIVE",
            )
            db.add(tank_pms_lag)
            db.flush()

            db.add(TankController(
                device_uid="TC-FCC-LAG-T1",
                tank_id=tank_pms_lag.id,
                connection_mode="SIM",
                signal_strength_dbm=-75,
                modbus_address=1,
                is_online=True,
            ))

            disp_lag = Dispenser(
                station_id=st_lag.id,
                code="DISP-LAG-01",
                manufacturer="Gilbarco",
                model="Encore 500S",
                protocol="Gilbarco_TwoWire",
                interface="CurrentLoop",
                serial="GB-2026-4410B",
                status="ACTIVE",
                totalizer_l=98500.0,
            )
            db.add(disp_lag)
            db.flush()

            nozzle_lag = Nozzle(
                dispenser_id=disp_lag.id,
                tank_id=tank_pms_lag.id,
                number=1,
                product_id=pms.id if pms else None,
                price=850.00,
                status="ACTIVE",
                totalizer_l=98500.0,
            )
            db.add(nozzle_lag)
            db.flush()

            db.add(FCCDevice(
                device_uid="FCC-S3-LAG-D1-N1",
                nozzle_id=nozzle_lag.id,
                firmware_version="v1.0.4-fcc",
                connection_mode="SIM",
                signal_strength_dbm=-74,
                calibration_factor=100.0,
                is_online=True,
            ))

        # 4. Station Manager (MGR001) assigned to Abuja Station
        manager = db.scalar(select(User).where(User.user_id == "MGR001"))
        if not manager:
            print("Creating Station Manager (MGR001)...")
            manager = User(
                user_id="MGR001",
                full_name="Abuja Forecourt Manager",
                role_id=manager_role.id,
                phone="+2348050000003",
                email="manager.abj@visualeyes360.ng",
                password_hash=hash_password("Manager@5678"),
                is_super_admin=False,
                is_active=True,
                all_stations=False,
                must_change_password=False,
            )
            if st_abj:
                manager.stations.append(st_abj)
            db.add(manager)
            db.flush()

            # Grant core permissions
            all_perms = db.scalars(select(Permission)).all()
            for perm in all_perms:
                if perm.module_code in [
                    "dashboard", "stations", "dispensers", "nozzles",
                    "fcc_devices", "tanks", "tank_controllers",
                    "transactions", "pulser", "tank_reconciliation",
                    "alerts", "reports"
                ]:
                    db.add(UserPermission(user_id=manager.id, permission_id=perm.id, effect="GRANT"))

        # 5. Special Customer with RFID Wallet
        cust1 = db.scalar(select(Customer).where(Customer.phone == "+2348061112233"))
        if not cust1:
            print("Creating Special Customers with RFID Wallets...")
            cust1 = Customer(
                full_name="Dangote Cement Transport Fleet",
                phone="+2348061112233",
                email="fleet@dangote.com",
                category="CORPORATE",
            )
            db.add(cust1)
            db.flush()

            # Wallet with balance
            db.add(Wallet(
                customer_id=cust1.id,
                balance=450000.00,
                reserved_balance=0.00,
            ))
            # Registered RFID Card
            db.add(RFIDCard(
                card_uid="RFID-NG-9812401",
                customer_id=cust1.id,
                auth_key_hash="hash-sec-key-001",
                is_blocked=False,
                daily_spend_limit=500000.00,
            ))

            # VIP Retail Customer
            cust2 = Customer(
                full_name="Alhaji Bello Kano (VIP)",
                phone="+2348094445566",
                email="bello.kano@gmail.com",
                category="VIP",
            )
            db.add(cust2)
            db.flush()
            db.add(Wallet(customer_id=cust2.id, balance=85000.00, reserved_balance=0.00))
            db.add(RFIDCard(
                card_uid="RFID-NG-5520109",
                customer_id=cust2.id,
                auth_key_hash="hash-sec-key-002",
                is_blocked=False,
                daily_spend_limit=150000.00,
            ))

        # 6. Fleet Management
        flt = db.scalar(select(Fleet).where(Fleet.code == "FLT-DNG-01"))
        if not flt:
            print("Creating Fleet and Commercial Vehicles...")
            flt = Fleet(
                name="Dangote Logistics North-Central",
                code="FLT-DNG-01",
                organization="Dangote Group",
                spending_limit=2500000.0,
            )
            db.add(flt)
            db.flush()

            db.add(Vehicle(
                fleet_id=flt.id,
                plate_number="ABJ-412-XA",
                vehicle_type="TRUCK",
                driver_name="Haruna Usman",
                fuel_type="AGO",
                spending_limit=120000.0,
                odometer_km=48200.0,
            ))
            db.add(Vehicle(
                fleet_id=flt.id,
                plate_number="LAG-889-KT",
                vehicle_type="VAN",
                driver_name="Emeka Eze",
                fuel_type="PMS",
                spending_limit=60000.0,
                odometer_km=21400.0,
            ))

        # 7. Realistic Transactions (including normal & 0.49L discrepancy incident)
        existing_tx = db.scalar(select(FuelTransaction))
        if not existing_tx and st_abj:
            print("Seeding realistic forecourt transactions with CPU vs Pulser verification...")
            d1 = db.scalar(select(Dispenser).where(Dispenser.station_id == st_abj.id))
            n1 = db.scalar(select(Nozzle).where(Nozzle.dispenser_id == d1.id, Nozzle.number == 1)) if d1 else None
            n2 = db.scalar(select(Nozzle).where(Nozzle.dispenser_id == d1.id, Nozzle.number == 2)) if d1 else None

            if n1 and n2:
                # Transaction 1: Normal Verified Transaction
                db.add(FuelTransaction(
                    transaction_ref="TXN-20261123-001-A",
                    station_id=st_abj.id,
                    dispenser_id=d1.id,
                    nozzle_id=n1.id,
                    fcc_device_id=n1.fcc.id if n1.fcc else None,
                    payment_channel="OPAY_POS",
                    payment_ref="OPAY-PAY-9921448A",
                    unit_price=850.00,
                    requested_amount=10000.00,
                    requested_volume=11.765,
                    dispenser_cpu_volume=11.765,
                    independent_pulser_volume=11.758,
                    raw_pulse_count=1175,
                    volume_difference=0.007,
                    discrepancy_alert=False,
                    investigation_status="NORMAL",
                    total_amount_billed=10000.00,
                    status="COMPLETED",
                ))

                # Transaction 2: Discrepancy Incident (0.750 L > 0.490 L threshold!)
                tx_disc = FuelTransaction(
                    transaction_ref="TXN-20261123-002-DISC",
                    station_id=st_abj.id,
                    dispenser_id=d1.id,
                    nozzle_id=n1.id,
                    fcc_device_id=n1.fcc.id if n1.fcc else None,
                    payment_channel="OPAY_POS",
                    payment_ref="OPAY-PAY-9921449B",
                    unit_price=850.00,
                    requested_amount=21250.00,
                    requested_volume=25.000,
                    dispenser_cpu_volume=25.000,
                    independent_pulser_volume=24.250,  # 0.750L short!
                    raw_pulse_count=2425,
                    volume_difference=0.750,
                    discrepancy_alert=True,
                    investigation_status="UNDER_REVIEW",
                    investigation_notes="Customer paid for 25.000 L. Dispenser CPU reported 25.000 L, but independent optical pulser counted only 24.250 L. Discrepancy of 0.750 L exceeds 0.49L threshold.",
                    total_amount_billed=21250.00,
                    status="COMPLETED",
                )
                db.add(tx_disc)
                db.flush()

                # Generate Critical Alert for this discrepancy
                db.add(SystemAlert(
                    station_id=st_abj.id,
                    alert_type="PULSER_DISCREPANCY",
                    severity="CRITICAL",
                    title="Pulser Discrepancy: 0.750 L on DISP-01 (Nozzle 1)",
                    description="Transaction TXN-20261123-002-DISC: Dispenser CPU reported 25.000 L, but Independent Pulser verified only 24.250 L (Delta = 0.750 L > 0.490 L). Possible flow diversion or meter slip.",
                    entity_type="transaction",
                    entity_id=tx_disc.id,
                ))

                # Transaction 3: RFID Wallet Transaction
                db.add(FuelTransaction(
                    transaction_ref="TXN-20261123-003-RFID",
                    station_id=st_abj.id,
                    dispenser_id=d1.id,
                    nozzle_id=n2.id,
                    fcc_device_id=n2.fcc.id if n2.fcc else None,
                    customer_id=cust1.id if cust1 else None,
                    payment_channel="RFID_WALLET",
                    payment_ref="WALLET-RES-882141",
                    unit_price=1150.00,
                    requested_amount=35000.00,
                    requested_volume=30.435,
                    dispenser_cpu_volume=30.435,
                    independent_pulser_volume=30.420,
                    raw_pulse_count=3042,
                    volume_difference=0.015,
                    discrepancy_alert=False,
                    investigation_status="NORMAL",
                    total_amount_billed=35000.00,
                    status="COMPLETED",
                ))

        # 8. Tank Reconciliation Record
        if st_abj:
            tank_abj = db.scalar(select(Tank).where(Tank.station_id == st_abj.id))
            if tank_abj:
                db.add(TankReconciliation(
                    tank_id=tank_abj.id,
                    station_id=st_abj.id,
                    shift_date=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                    opening_stock_l=36800.0,
                    deliveries_l=0.0,
                    sales_cpu_l=2550.0,
                    sales_pulser_l=2548.2,
                    expected_closing_stock_l=34250.0,
                    actual_atg_closing_stock_l=34248.0,
                    variance_l=-2.0,
                    variance_percentage=0.006,
                    status="NORMAL",
                ))

        # 9. Initial Security Alert for Lagos Station (Cover opened)
        if st_lag:
            db.add(SystemAlert(
                station_id=st_lag.id,
                alert_type="TANK_HATCH_OPEN",
                severity="CRITICAL",
                title="Unauthorized Tank Hatch Open: TANK-LAG-01-PMS",
                description="Manhole cover sensor tripped on Tank 1 at Victoria Island Express Station. Duration: active. Security footage review required.",
                entity_type="tank",
                is_resolved=False,
            ))

        db.commit()
        print("\n========================================================")
        print("VISUAL EYES 360 SEED COMPLETE!")
        print("👑 Superior Administrator: SUPERADMIN001 | Admin@1234")
        print("💼 Station Manager:        MGR001         | Manager@5678")
        print("========================================================\n")


if __name__ == "__main__":
    seed()
