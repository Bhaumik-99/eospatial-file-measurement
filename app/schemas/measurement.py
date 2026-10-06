from typing import Any

from pydantic import BaseModel


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
    items: list[MeasurementItem]
