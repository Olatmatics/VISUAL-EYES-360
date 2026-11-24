"""Device-ingest service entrypoint.

Same codebase as the management API, but a separate process so telemetry and
journal replay cannot starve payment verification or dispensing authorization.
Public traffic reaches this app through ``/api/v1/device-ingest/*``.
"""

from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.cache import close_cache
from app.core.config import settings
from app.db.base import get_db
from app.modules.device_ingest.router import router as device_ingest_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    close_cache()


production = settings.ENVIRONMENT.lower() in {"production", "prod", "live"}

app = FastAPI(
    title=f"{settings.APP_NAME} — Device Ingest",
    version="1.0.0",
    description="Device telemetry and journal ingestion. Isolated from management traffic.",
    docs_url=None if production else "/docs",
    redoc_url=None if production else "/redoc",
    openapi_url=None if production else "/openapi.json",
    lifespan=lifespan,
)

app.include_router(device_ingest_router)


@app.get("/health", tags=["system"])
def health(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=503, detail="Database unavailable") from exc
    return {"status": "ok", "service": "ingest", "environment": settings.ENVIRONMENT}
