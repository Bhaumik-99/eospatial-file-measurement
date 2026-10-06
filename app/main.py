from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import ORJSONResponse

from app.api.files import router as files_router
from app.core.config import get_settings
from app.db.session import Base, engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    get_settings().storage_dir.mkdir(parents=True, exist_ok=True)
    yield


settings = get_settings()
app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    description=(
        "Uploads Shapefile ZIP/KML datasets and returns CRS-aware per-feature measurements."
    ),
    default_response_class=ORJSONResponse,
    lifespan=lifespan,
)

app.include_router(files_router)


@app.get("/healthz", tags=["Health"])
def healthz():
    return {"status": "ok"}
