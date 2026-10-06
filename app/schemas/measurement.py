from typing import Any

from pydantic import BaseModel, Field


class MeasurementItem(BaseModel):
    feature_id: int
    geometry_type: str
    geometry: dict[str, Any] | None
    properties: dict[str, Any]
    crs: str | None
    measurement_crs: str | None
    measurement_supported: bool
    area_m2: float | None = None
    length_m: float | None = None


class MeasurementResponse(BaseModel):
    file_id: str
    feature_count: int
    file_crs: str | None
    page: int = Field(ge=1)
    page_size: int = Field(ge=1)
    total: int = Field(ge=0)
    has_next: bool
    items: list[MeasurementItem]
