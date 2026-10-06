from __future__ import annotations

import json
import math
import numbers
import zipfile
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory

import geopandas as gpd
import pyogrio
from pyproj import CRS
from shapely.geometry import mapping

from app.core.config import Settings


class GeospatialProcessingError(ValueError):
    pass


@dataclass(frozen=True)
class ProjectionPlan:
    original_crs: str | None
    area_crs: str | None
    length_crs: str | None


@dataclass(frozen=True)
class ProcessedFeature:
    feature_index: int
    geometry_type: str
    geometry: dict | None
    properties: dict
    crs: str | None
    measurement_crs: str | None
    area_m2: float | None
    length_m: float | None
    measurement_supported: bool


@dataclass(frozen=True)
class ProcessedFile:
    file_type: str
    feature_count: int
    crs: str | None
    features: list[ProcessedFeature]


def _crs_label(crs: CRS | None) -> str | None:
    if crs is None:
        return None
    authority = crs.to_authority()
    return f"{authority[0]}:{authority[1]}" if authority else crs.to_string()


def _sanitize_json(value):
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, numbers.Integral):
        return int(value)
    if isinstance(value, numbers.Real):
        return float(value)
    if hasattr(value, "item"):
        return _sanitize_json(value.item())
    if isinstance(value, dict):
        return {str(k): _sanitize_json(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_sanitize_json(v) for v in value]
    try:
        json.dumps(value)
        return value
    except TypeError:
        return str(value)


def _safe_extract(
    zip_path: Path, output_dir: Path, max_bytes: int, max_files: int = 10_000
) -> None:
    try:
        with zipfile.ZipFile(zip_path) as archive:
            if archive.testzip():
                raise GeospatialProcessingError("ZIP archive is corrupt.")
            total_uncompressed = 0
            file_count = 0
            for info in archive.infolist():
                if info.is_dir():
                    continue
                file_count += 1
                if file_count > max_files:
                    raise GeospatialProcessingError("ZIP contains too many files.")
                file_count += 1
                if file_count > max_files:
                    raise GeospatialProcessingError("ZIP contains too many files.")
                name = Path(info.filename)
                if name.is_absolute() or ".." in name.parts:
                    raise GeospatialProcessingError("ZIP contains an unsafe path.")
                if info.create_system == 3 and ((info.external_attr >> 16) & 0o170000) == 0o120000:
                    raise GeospatialProcessingError("ZIP contains an unsafe symbolic link.")
                if info.create_system == 3 and (
                    (info.external_attr >> 16) & 0o170000
                ) == 0o120000:
                    raise GeospatialProcessingError("ZIP contains an unsafe symbolic link.")
                total_uncompressed += info.file_size
                if total_uncompressed > max_bytes:
                    raise GeospatialProcessingError(
                        "Extracted ZIP contents exceed the configured limit."
                    )
                target = output_dir / name
                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(info) as source, target.open("wb") as destination:
                    while chunk := source.read(1024 * 1024):
                        destination.write(chunk)
    except zipfile.BadZipFile as exc:
        raise GeospatialProcessingError("Uploaded ZIP archive is invalid.") from exc


def _find_shapefile(extracted_dir: Path) -> Path:
    shapefiles = sorted(extracted_dir.rglob("*.shp")) + sorted(extracted_dir.rglob("*.SHP"))
    unique = []
    seen = set()
    for path in shapefiles:
        key = path.resolve()
        if key not in seen:
            seen.add(key)
            unique.append(path)
    if not unique:
        raise GeospatialProcessingError("ZIP does not contain a .shp file.")
    if len(unique) > 1:
        raise GeospatialProcessingError(
            "ZIP contains multiple shapefiles; upload one dataset per archive."
        )
    return unique[0]


def _read_dataset(path: Path) -> gpd.GeoDataFrame:
    try:
        layers = pyogrio.list_layers(path)
        if len(layers) == 0:
            raise GeospatialProcessingError("No readable geospatial layers were found.")
        layer_name = str(layers[0][0])
        return pyogrio.read_dataframe(path, layer=layer_name, read_geometry=True)
    except GeospatialProcessingError:
        raise
    except Exception as exc:
        raise GeospatialProcessingError(f"Unable to read geospatial data: {exc}") from exc


def _representative_lon_lat(gdf: gpd.GeoDataFrame) -> tuple[float, float]:
    wgs84 = gdf.to_crs("EPSG:4326") if gdf.crs else gdf
    point = wgs84.geometry.union_all().representative_point()
    return float(point.x), float(point.y)


def _local_crs(prefix: str, lon: float, lat: float) -> str:
    return (
        f"+proj={prefix} +lat_0={lat:.8f} +lon_0={lon:.8f} "
        "+datum=WGS84 +units=m +no_defs"
    )


def _projection_plan(gdf: gpd.GeoDataFrame) -> ProjectionPlan:
    original = _crs_label(gdf.crs)
    if gdf.crs is None:
        return ProjectionPlan(original_crs=None, area_crs=None, length_crs=None)

    crs = CRS.from_user_input(gdf.crs)
    if crs.is_projected:
        axis = crs.axis_info[0] if crs.axis_info else None
        unit_name = (axis.unit_name or "").lower() if axis else ""
        unit_factor = axis.unit_conversion_factor if axis else None
        uses_metres = unit_name in {"metre", "meter", "metres", "meters"} and (
            unit_factor is None or abs(unit_factor - 1.0) < 1e-9
        )
        if uses_metres:
            return ProjectionPlan(original, original, original)
        gdf = gdf.to_crs("EPSG:4326")

    wgs84 = gdf.to_crs("EPSG:4326") if gdf.crs != CRS.from_user_input("EPSG:4326") else gdf
    lon, lat = _representative_lon_lat(wgs84)
    minx, miny, maxx, maxy = wgs84.total_bounds
    lon_span = abs(maxx - minx)
    lat_span = abs(maxy - miny)

    if lon_span <= 12 and lat_span <= 8 and -80 <= lat <= 84:
        try:
            estimated = wgs84.estimate_utm_crs()
            if estimated:
                label = _crs_label(CRS.from_user_input(estimated))
                return ProjectionPlan(original, label, label)
        except Exception:
            pass

    if -90 < lat < 90:
        return ProjectionPlan(
            original,
            _local_crs("laea", lon, lat),
            _local_crs("aeqd", lon, lat),
        )

    raise GeospatialProcessingError("Could not select a projected CRS for measurement.")


def _measurement(geometry, source_crs, plan: ProjectionPlan):
    if geometry is None or geometry.is_empty:
        return None, None, plan.original_crs, False

    geometry_type = geometry.geom_type
    supported_types = {
        "Polygon",
        "MultiPolygon",
        "LineString",
        "MultiLineString",
        "Point",
        "MultiPoint",
    }
    if geometry_type not in supported_types:
        return None, None, plan.original_crs, False

    if geometry_type in {"Polygon", "MultiPolygon"}:
        if not plan.area_crs or source_crs is None:
            return None, None, None, False
        projected = gpd.GeoSeries([geometry], crs=source_crs).to_crs(plan.area_crs).iloc[0]
        return float(projected.area), None, plan.area_crs, True

    if geometry_type in {"LineString", "MultiLineString"}:
        if not plan.length_crs or source_crs is None:
            return None, None, None, False
        projected = (
            gpd.GeoSeries([geometry], crs=source_crs).to_crs(plan.length_crs).iloc[0]
        )
        return None, float(projected.length), plan.length_crs, True

    return None, None, plan.original_crs, True


def process_geospatial_file(path: Path, file_type: str, settings: Settings) -> ProcessedFile:
    with TemporaryDirectory(prefix="geo-measure-") as temp_dir:
        working = Path(temp_dir)
        dataset_path = path
        if file_type == "shapefile-zip":
            _safe_extract(
                path,
                working,
                settings.max_extracted_size_bytes,
                settings.max_zip_files,
            )
            dataset_path = _find_shapefile(working)
        elif file_type != "kml":
            raise GeospatialProcessingError("Unsupported file type.")

        gdf = _read_dataset(dataset_path)
        if len(gdf) > settings.max_features:
            raise GeospatialProcessingError(
                f"Dataset contains {len(gdf):,} features; limit is {settings.max_features:,}."
            )

        plan = _projection_plan(gdf)
        original_crs = plan.original_crs
        features: list[ProcessedFeature] = []
        for position, (idx, row) in enumerate(gdf.iterrows()):
            geometry = row.geometry
            properties = {
                str(key): _sanitize_json(value)
                for key, value in row.items()
                if key != "geometry"
            }
            area_m2, length_m, measurement_crs, supported = _measurement(
                geometry, gdf.crs, plan
            )
            features.append(
                ProcessedFeature(
                    feature_index=int(idx) if isinstance(idx, numbers.Integral) else position,
                    geometry_type=geometry.geom_type if geometry is not None else "Unknown",
                    geometry=_sanitize_json(mapping(geometry)) if geometry is not None else None,
                    properties=properties,
                    crs=original_crs,
                    measurement_crs=measurement_crs,
                    area_m2=area_m2,
                    length_m=length_m,
                    measurement_supported=supported,
                )
            )

        return ProcessedFile(
            file_type=file_type,
            feature_count=len(features),
            crs=original_crs,
            features=features,
        )
