from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from app.core.deps import allowed_station_ids, get_current_user
from app.db.base import get_db
from app.models.auth import User
from app.models.core import Dispenser, FuelProduct, FuelTransaction, Nozzle, Station, SystemAlert, Tank

router = APIRouter(prefix="/api/v1/reports", tags=["reports"])


@router.get("/summary")
def generate_summary_report(station_id: str | None = None, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    stmt_tx = select(FuelTransaction)
    allowed = allowed_station_ids(user)
    if allowed is not None:
        stmt_tx = stmt_tx.where(FuelTransaction.station_id.in_(allowed))
    if station_id:
        stmt_tx = stmt_tx.where(FuelTransaction.station_id == station_id)

    txs = db.scalars(stmt_tx).all()

    total_revenue = sum(t.total_amount_billed for t in txs)
    total_volume_cpu = sum(t.dispenser_cpu_volume for t in txs)
    total_volume_pulser = sum(t.independent_pulser_volume for t in txs)
    discrepancy_count = sum(1 for t in txs if t.discrepancy_alert)

    # Product breakdown
    pms_vol = sum(t.dispenser_cpu_volume for t in txs if t.nozzle and t.nozzle.product and t.nozzle.product.code == "PMS")
    ago_vol = sum(t.dispenser_cpu_volume for t in txs if t.nozzle and t.nozzle.product and t.nozzle.product.code == "AGO")
    dpk_vol = sum(t.dispenser_cpu_volume for t in txs if t.nozzle and t.nozzle.product and t.nozzle.product.code == "DPK")

    # Payment channel breakdown
    opay_vol = sum(t.total_amount_billed for t in txs if t.payment_channel == "OPAY_POS")
    wallet_vol = sum(t.total_amount_billed for t in txs if t.payment_channel == "RFID_WALLET")
    transfer_vol = sum(t.total_amount_billed for t in txs if t.payment_channel == "BANK_TRANSFER")

    # Tank inventory
    stmt_tanks = select(Tank)
    if allowed is not None:
        stmt_tanks = stmt_tanks.where(Tank.station_id.in_(allowed))
    if station_id:
        stmt_tanks = stmt_tanks.where(Tank.station_id == station_id)
    tanks = db.scalars(stmt_tanks).all()
    total_capacity = sum(t.capacity_l for t in tanks)
    total_stock = sum(t.current_volume_l for t in tanks)

    return {
        "financial": {
            "total_revenue_ngn": round(total_revenue, 2),
            "opay_pos_ngn": round(opay_vol, 2),
            "rfid_wallet_ngn": round(wallet_vol, 2),
            "bank_transfer_ngn": round(transfer_vol, 2),
        },
        "volumetric": {
            "total_dispensed_cpu_l": round(total_volume_cpu, 2),
            "total_verified_pulser_l": round(total_volume_pulser, 2),
            "measurement_difference_l": round(abs(total_volume_cpu - total_volume_pulser), 3),
            "pms_volume_l": round(pms_vol, 2),
            "ago_volume_l": round(ago_vol, 2),
            "dpk_volume_l": round(dpk_vol, 2),
        },
        "inventory": {
            "total_storage_capacity_l": total_capacity,
            "current_physical_stock_l": round(total_stock, 2),
            "ullage_available_l": round(max(0.0, total_capacity - total_stock), 2),
            "stock_fill_percentage": round((total_stock / total_capacity * 100), 1) if total_capacity > 0 else 0,
        },
        "compliance": {
            "total_transactions": len(txs),
            "discrepancy_incidents": discrepancy_count,
            "compliance_rate_percent": round((1 - (discrepancy_count / len(txs))) * 100, 1) if txs else 100.0,
            "active_unresolved_alerts": db.scalar(select(func.count(SystemAlert.id)).where(SystemAlert.is_resolved.is_(False))) or 0,
        }
    }
