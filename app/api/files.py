import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.models.file import FileRecord, FileStatus
from app.models.measurement import FeatureMeasurement
from app.schemas.file import FileDetailResponse, FileUploadResponse
from app.schemas.measurement import MeasurementItem, MeasurementResponse
from app.services.geospatial import process_geospatial_file
from app.services.processing import persist_processed_file
from app.services.storage import StorageLimitError, safe_filename, save_upload

router = APIRouter(prefix="/api/files", tags=["Files"])


def _file_type(filename: str) -> str:
    suffix = Path(filename).suffix.lower()
    if suffix == ".kml":
        return "kml"
    if suffix == ".zip":
        return "shapefile-zip"
    raise HTTPException(
        status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
        detail="Only .kml files and .zip archives containing a Shapefile are supported.",
    )


def _get_file_or_404(file_id: str, db: Session) -> FileRecord:
    record = db.scalar(select(FileRecord).where(FileRecord.id == file_id))
    if not record:
        raise HTTPException(status_code=404, detail="File not found.")
    return record


@router.post("/", response_model=FileUploadResponse, status_code=201)
async def upload_file(
    upload: UploadFile = File(...),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    filename = safe_filename(upload.filename)
    file_type = _file_type(filename)
    file_id = str(uuid.uuid4())
    destination = settings.storage_dir / file_id / filename
    record = FileRecord(
        id=file_id,
        filename=filename,
        stored_path=str(destination.resolve()),
        file_type=file_type,
        status=FileStatus.PROCESSING,
    )
    db.add(record)
    db.commit()
    db.refresh(record)

    try:
        await save_upload(upload, destination, settings)
        processed = await run_in_threadpool(
            process_geospatial_file, destination, file_type, settings
        )
        persist_processed_file(db, record, processed)
    except StorageLimitError as exc:
        record.status = FileStatus.FAILED
        record.error_message = str(exc)
        db.commit()
        raise HTTPException(status_code=413, detail=str(exc)) from exc
    except Exception as exc:
        record.status = FileStatus.FAILED
        record.error_message = str(exc)
        db.commit()

    return FileUploadResponse.model_validate(record)


@router.get("/{file_id}/", response_model=FileDetailResponse)
def get_file(file_id: str, db: Session = Depends(get_db)):
    return _get_file_or_404(file_id, db)


@router.get("/{file_id}/measurements/", response_model=MeasurementResponse)
def get_measurements(file_id: str, db: Session = Depends(get_db)):
    record = _get_file_or_404(file_id, db)
    rows = db.scalars(
        select(FeatureMeasurement)
        .where(FeatureMeasurement.file_id == file_id)
        .order_by(FeatureMeasurement.feature_index)
    ).all()

    if record.status == FileStatus.PROCESSING:
        raise HTTPException(status_code=409, detail="File processing is still in progress.")
    if record.status == FileStatus.FAILED:
        raise HTTPException(
            status_code=422,
            detail=record.error_message or "File processing failed.",
        )

    return MeasurementResponse(
        file_id=file_id,
        feature_count=record.feature_count,
        file_crs=record.crs,
        items=[
            MeasurementItem(
                feature_id=row.feature_index,
                geometry_type=row.geometry_type,
                geometry=row.geometry,
                properties=row.properties,
                crs=row.crs,
                measurement_crs=row.measurement_crs,
                measurement_supported=row.measurement_supported,
                area_m2=row.area_m2,
                length_m=row.length_m,
            )
            for row in rows
        ],
    )
