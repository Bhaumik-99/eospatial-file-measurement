from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict


class FileStatus(str, Enum):
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class FileUploadResponse(BaseModel):
    id: str
    filename: str
    feature_count: int
    crs: str | None
    status: FileStatus

    model_config = ConfigDict(from_attributes=True)


class FileDetailResponse(FileUploadResponse):
    file_type: str
    error_message: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
