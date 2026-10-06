# Geospatial File Measurement API

FastAPI service for uploading KML files or ZIP archives containing Shapefiles, extracting geospatial features, and calculating CRS-aware area/length measurements.

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Open `/docs` for Swagger UI.

## API

- `POST /api/files/` upload `.kml` or `.zip` Shapefile archive.
- `GET /api/files/{id}/` file status and metadata.
- `GET /api/files/{id}/measurements/` per-feature measurements.
- `GET /healthz` health check.

### Example

```bash
curl -X POST http://localhost:8000/api/files/ -F "upload=@examples/demo.kml"
curl http://localhost:8000/api/files/<id>/
curl http://localhost:8000/api/files/<id>/measurements/
```

## Architecture

`app/api` exposes HTTP endpoints; `app/services` owns storage, parsing, CRS selection and measurement calculation; `app/models` persists file/feature measurement records through SQLAlchemy; `tests` cover API, geospatial behavior, KML, and security.

Processing flow: validate extension and size -> persist PROCESSING record -> validate content -> queue background processing -> extract KML or ZIP Shapefile -> load features with GDAL/Pyogrio -> normalize metadata -> select measurement CRS -> calculate measurements -> persist results -> mark COMPLETED or FAILED.

## CRS handling

Area and distance are never calculated directly in geographic longitude/latitude degrees. Geographic datasets are transformed into a suitable projected CRS before measurement. Compact extents prefer a local UTM zone; wider extents use a Lambert Azimuthal Equal Area / Azimuthal Equidistant strategy around the dataset centroid.

## Security and reliability

ZIP extraction blocks path traversal, rejects unsafe symlinks, limits compressed/uncompressed size, archive file count, and feature count, and requires Shapefile component files. Upload size and feature-count limits are configurable through environment variables. Invalid files move to `FAILED` with a user-facing error instead of crashing the API.

## Design decisions

FastAPI was selected for typed request/response models and automatic OpenAPI documentation. GeoPandas/Pyogrio/GDAL provide mature format and CRS support instead of maintaining custom parsers. SQLite is the default for easy local execution while SQLAlchemy keeps persistence replaceable. FastAPI background tasks provide immediate `202 Accepted` behavior for this assignment; a durable external queue is the natural next step for multi-process production deployments.

## Learning and future scope

This project reinforced practical geospatial concepts such as CRS selection, projected-vs-geographic measurement semantics, safe archive extraction, and separation of API, processing, and persistence concerns. Future work includes durable background job queues, PostGIS, object storage, pagination/streaming for large feature sets, richer geometry support, observability, authentication/rate limiting, and cloud deployment.

## Tests

```bash
pytest
```

## Docker

```bash
docker compose up --build
```

License: MIT.


## Geometry behavior

| Geometry | Result |
|---|---|
| Polygon / MultiPolygon | area_m2 |
| LineString / MultiLineString | length_m |
| Point / MultiPoint | no measurement required |
| Other geometry types | stored and marked unsupported |

Every feature response includes feature ID/index, geometry type, original geometry, CRS, properties, measurement CRS, and the applicable measurement.

## Example response

```json
{
  "id": "abc123",
  "filename": "survey.kml",
  "feature_count": 120,
  "crs": "EPSG:4326",
  "status": "COMPLETED"
}
```

## Configuration

| Variable | Default | Purpose |
|---|---:|---|
| DATABASE_URL | sqlite:///./app.db | SQLAlchemy database URL |
| STORAGE_DIR | ./storage | uploaded-file storage |
| MAX_UPLOAD_SIZE_MB | 50 | upload size limit |
| MAX_EXTRACTED_SIZE_MB | 200 | extracted ZIP size limit |
| MAX_FEATURES | 100000 | feature-count guardrail |
| MAX_ZIP_FILES | 10000 | archive file-count guardrail |

## Learning

Key learning areas were CRS-aware measurement, GDAL-backed ingestion, Shapefile archive handling, safe extraction, typed FastAPI contracts, and separating geospatial processing from persistence.

## Future scope

- Background worker queue with 202 Accepted jobs for large datasets
- PostgreSQL/PostGIS and object storage
- Pagination and streaming for large feature collections
- More OGC formats and richer spatial filters
- Authentication, rate limiting, structured logging, and OpenTelemetry


## Operations

`DELETE /api/files/{id}/` removes the database record, feature results, and local upload directory. The measurement endpoint supports pagination and `include_geometry=false` for smaller responses.

## Database migrations

Versioned schema evolution is provided through Alembic:

```bash
alembic upgrade head
```


`AUTO_CREATE_SCHEMA` defaults to `true` for local setup. Set it to `false` in controlled deployments and run `alembic upgrade head` before starting the application.
