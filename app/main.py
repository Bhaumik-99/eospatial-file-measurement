import logging
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import ORJSONResponse
from sqlalchemy import text

from app.api.files import router as files_router
from app.core.config import get_settings
from app.db.session import Base, SessionLocal, engine

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    if settings.auto_create_schema:
        Base.metadata.create_all(bind=engine)
    settings.storage_dir.mkdir(parents=True, exist_ok=True)
    yield


settings = get_settings()
app = FastAPI(
    title=settings.app_name,
    version="2.0.0",
    description=(
        "Uploads Shapefile ZIP/KML datasets and returns CRS-aware per-feature measurements."
    ),
    default_response_class=ORJSONResponse,
    lifespan=lifespan,
)


@app.middleware("http")
async def request_context(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


app.include_router(files_router)


@app.get("/healthz", tags=["Health"])
def healthz():
    db = SessionLocal()
    try:
        db.execute(text("SELECT 1"))
        return {"status": "ok", "database": "ok", "storage": "ok"}
    finally:
        db.close()
