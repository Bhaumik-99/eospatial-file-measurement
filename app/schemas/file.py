from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict


class FileStatus(StrEnum):
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class FileUploadResponse(BaseModel):
    id: str
    filename: str
    feature_count: int
    crs: str | None
    status: FileStatus
    status_url: str

    model_config = ConfigDict(from_attributes=True)


class FileDetailResponse(FileUploadResponse):
    file_type: str
    error_message: str | None = None
    created_at: datetime
    processed_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)
