from pathlib import Path

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models.file import FileRecord, FileStatus
from app.models.measurement import FeatureMeasurement
from app.services.geospatial import ProcessedFile, process_geospatial_file


def persist_processed_file(db: Session, record: FileRecord, processed: ProcessedFile) -> None:
    record.feature_count = processed.feature_count
    record.crs = processed.crs
    record.status = FileStatus.COMPLETED
    record.error_message = None

    db.query(FeatureMeasurement).filter(FeatureMeasurement.file_id == record.id).delete()
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


def process_file_record(db: Session, record: FileRecord, settings: Settings) -> None:
    """Synchronous service entry point useful to workers/CLI jobs."""
    try:
        processed = process_geospatial_file(Path(record.stored_path), record.file_type, settings)
        persist_processed_file(db, record, processed)
    except Exception as exc:
        db.rollback()
        record.status = FileStatus.FAILED
        record.error_message = str(exc)
        db.commit()
