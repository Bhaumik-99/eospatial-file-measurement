import logging
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.session import get_session_factory
from app.models.file import FileRecord, FileStatus
from app.models.measurement import FeatureMeasurement
from app.services.geospatial import (
    GeospatialProcessingError,
    ProcessedFile,
    process_geospatial_file,
)

logger = logging.getLogger(__name__)


def persist_processed_file(db: Session, record: FileRecord, processed: ProcessedFile) -> None:
    record.feature_count = processed.feature_count
    record.crs = processed.crs
    record.status = FileStatus.COMPLETED
    record.error_message = None
    record.processed_at = datetime.now(timezone.utc)

    db.query(FeatureMeasurement).filter(FeatureMeasurement.file_id == record.id).delete(
        synchronize_session=False
    )
    db.add_all(
        [
            FeatureMeasurement(
                file_id=record.id,
                feature_index=feature.feature_index,
                geometry_type=feature.geometry_type,
                geometry=feature.geometry
                or {"type": "GeometryCollection", "geometries": []},
                properties=feature.properties,
                crs=feature.crs,
                measurement_crs=feature.measurement_crs,
                area_m2=feature.area_m2,
                length_m=feature.length_m,
                measurement_supported=feature.measurement_supported,
            )
            for feature in processed.features
        ]
    )
    db.commit()


def process_file_record(file_id: str, settings: Settings) -> None:
    """Process one file using a fresh database session for background/worker execution."""
    session_factory = get_session_factory(settings.database_url)
    db = session_factory()
    try:
        record = db.get(FileRecord, file_id)
        if record is None or record.status != FileStatus.PROCESSING:
            return

        processed = process_geospatial_file(Path(record.stored_path), record.file_type, settings)
        persist_processed_file(db, record, processed)
        logger.info("Geospatial file processed", extra={"file_id": file_id})
    except GeospatialProcessingError as exc:
        db.rollback()
        record = db.get(FileRecord, file_id)
        if record:
            record.status = FileStatus.FAILED
            record.error_message = str(exc)
            record.processed_at = datetime.now(timezone.utc)
            db.commit()
        logger.warning(
            "Geospatial file rejected",
            extra={"file_id": file_id, "reason": str(exc)},
        )
    except Exception:
        db.rollback()
        record = db.get(FileRecord, file_id)
        if record:
            record.status = FileStatus.FAILED
            record.error_message = "Unexpected processing error. Check application logs."
            record.processed_at = datetime.now(timezone.utc)
            db.commit()
        logger.exception(
            "Unexpected geospatial processing failure",
            extra={"file_id": file_id},
        )
    finally:
        db.close()
