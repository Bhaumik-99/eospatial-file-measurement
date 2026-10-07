import logging
import uuid
from pathlib import Path

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    HTTPException,
    Query,
    UploadFile,
    status,
)
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.models.file import FileRecord, FileStatus
from app.models.measurement import FeatureMeasurement
from app.schemas.file import FileDetailResponse, FileUploadResponse
from app.schemas.measurement import MeasurementItem, MeasurementResponse
from app.services.processing import process_file_record
from app.services.storage import (
    StorageLimitError,
    UploadValidationError,
    remove_upload,
    safe_filename,
    save_upload,
    validate_saved_upload,
)

logger = logging.getLogger(__name__)
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


@router.post("/", response_model=FileUploadResponse, status_code=status.HTTP_202_ACCEPTED)
async def upload_file(
    background_tasks: BackgroundTasks,
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
        validate_saved_upload(destination, file_type)
    except StorageLimitError as exc:
        record.status = FileStatus.FAILED
        record.error_message = str(exc)
        db.commit()
        remove_upload(destination)
        raise HTTPException(status_code=413, detail=str(exc)) from exc
    except UploadValidationError as exc:
        record.status = FileStatus.FAILED
        record.error_message = str(exc)
        db.commit()
        remove_upload(destination)
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        db.rollback()
        logger.exception("Upload persistence failure", extra={"file_id": file_id})
        record = db.get(FileRecord, file_id)
        if record:
            record.status = FileStatus.FAILED
            record.error_message = "Unable to store uploaded file."
            db.commit()
        raise HTTPException(status_code=500, detail="Unable to store uploaded file.") from exc

    background_tasks.add_task(process_file_record, file_id, settings)

    return FileUploadResponse(
        id=record.id,
        filename=record.filename,
        feature_count=record.feature_count,
        crs=record.crs,
        status=FileStatus.PROCESSING,
        status_url=f"/api/files/{record.id}/",
    )


@router.get("/{file_id}/", response_model=FileDetailResponse)
def get_file(file_id: str, db: Session = Depends(get_db)):
    record = _get_file_or_404(file_id, db)
    return FileDetailResponse(
        id=record.id,
        filename=record.filename,
        feature_count=record.feature_count,
        crs=record.crs,
        status=record.status,
        status_url=f"/api/files/{record.id}/",
        file_type=record.file_type,
        error_message=record.error_message,
        created_at=record.created_at,
        processed_at=record.processed_at,
    )


@router.get("/{file_id}/measurements/", response_model=MeasurementResponse)
def get_measurements(
    file_id: str,
    page: int = Query(1, ge=1),
    page_size: int | None = Query(None, ge=1),
    include_geometry: bool = Query(True),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    record = _get_file_or_404(file_id, db)
    if record.status == FileStatus.PROCESSING:
        raise HTTPException(status_code=409, detail="File processing is still in progress.")
    if record.status == FileStatus.FAILED:
        raise HTTPException(
            status_code=422,
            detail=record.error_message or "File processing failed.",
        )

    resolved_page_size = page_size or settings.measurement_page_size_default
    if resolved_page_size > settings.measurement_page_size_max:
        raise HTTPException(
            status_code=422,
            detail=f"page_size cannot exceed {settings.measurement_page_size_max}.",
        )

    total = int(
        db.scalar(
            select(func.count(FeatureMeasurement.id)).where(FeatureMeasurement.file_id == file_id)
        )
        or 0
    )
    offset = (page - 1) * resolved_page_size
    rows = db.scalars(
        select(FeatureMeasurement)
        .where(FeatureMeasurement.file_id == file_id)
        .order_by(FeatureMeasurement.feature_index)
        .offset(offset)
        .limit(resolved_page_size)
    ).all()

    return MeasurementResponse(
        file_id=file_id,
        feature_count=record.feature_count,
        file_crs=record.crs,
        page=page,
        page_size=resolved_page_size,
        total=total,
        has_next=offset + len(rows) < total,
        items=[
            MeasurementItem(
                feature_id=row.feature_index,
                geometry_type=row.geometry_type,
                geometry=row.geometry if include_geometry else None,
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


@router.delete("/{file_id}/", status_code=status.HTTP_204_NO_CONTENT)
def delete_file(file_id: str, db: Session = Depends(get_db)):
    record = _get_file_or_404(file_id, db)
    storage_path = Path(record.stored_path)
    db.query(FeatureMeasurement).filter(FeatureMeasurement.file_id == file_id).delete(
        synchronize_session=False
    )
    db.delete(record)
    db.commit()
    remove_upload(storage_path)
    return None
