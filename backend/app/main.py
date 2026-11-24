import os

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, Response
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.base import get_db
from app.db.init_db import init_db
import app.models
from app.modules.alerts.router import router as alerts_router
from app.modules.auth.router import router as auth_router
from app.modules.customers.router import router as customers_router
from app.modules.dashboard.router import router as dashboard_router
from app.modules.device_ingest.router import router as device_ingest_router
from app.modules.forecourt.router import router as forecourt_router
from app.modules.geo.router import router as geo_router
from app.modules.operations.router import router as operations_router
from app.modules.payments.router import router as payments_router
from app.modules.prices.router import router as prices_router
from app.modules.reconciliation.router import router as reconciliation_router
from app.modules.settings.router import router as settings_router
from app.modules.reports.exports_router import router as reports_exports_router
from app.modules.reports.router import router as reports_router
from app.modules.stations.router import router as stations_router
from app.modules.tanks.router import router as tanks_router
from app.modules.transactions.router import router as transactions_router
from app.modules.users.router import router as users_router

# Multi-worker deployments run schema/seed once via the `migrate` service.
# Development and tests keep the original behaviour unchanged.
if os.getenv("VE360_SKIP_INIT") != "1":
    init_db()

production = settings.ENVIRONMENT.lower() in {"production", "prod", "live"}

app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
    description="Fuel station automation and industrial management platform — Complete backend",
    docs_url=None if production else "/docs",
    redoc_url=None if production else "/redoc",
    openapi_url=None if production else "/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register all forecourt IoT & management modules
for router in (
    auth_router,
    users_router,
    stations_router,
    dashboard_router,
    device_ingest_router,
    forecourt_router,
    geo_router,
    operations_router,
    tanks_router,
    transactions_router,
    reconciliation_router,
    payments_router,
    customers_router,
    prices_router,
    alerts_router,
    reports_router,
    reports_exports_router,
    settings_router,
):
    app.include_router(router)


@app.get("/", tags=["system"])
def root():
    return {
        "app": settings.APP_NAME,
        "status": "running",
        "api_docs": None if production else "/docs",
        "frontend_url": settings.PUBLIC_APP_URL,
        "message": "VISUAL EYES 360 Backend API is active.",
    }

@app.get("/health", tags=["system"])
def health(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=503, detail="Database unavailable") from exc
    return {"status": "ok", "app": settings.APP_NAME, "environment": settings.ENVIRONMENT}


@app.get("/setup/status", tags=["system"], include_in_schema=False)
def setup_status_alias():
    return RedirectResponse(url="/api/v1/setup/status")


@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    return Response(status_code=204)
