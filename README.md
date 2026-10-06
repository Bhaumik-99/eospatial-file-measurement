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
curl -X POST http://localhost:8000/api/files/ -F "file=@examples/demo.kml"
curl http://localhost:8000/api/files/<id>/
curl http://localhost:8000/api/files/<id>/measurements/
```

## Architecture

`app/api` exposes HTTP endpoints; `app/services` owns storage, parsing, CRS selection and measurement calculation; `app/models` persists file/feature measurement records through SQLAlchemy; `tests` cover API, geospatial behavior, KML, and security.

Processing flow: validate extension and size -> persist upload -> extract KML or ZIP Shapefile -> load features with GeoPandas -> normalize metadata -> select a measurement CRS -> calculate supported measurements -> persist results -> mark file completed.

## CRS handling

Area and distance are never calculated directly in geographic longitude/latitude degrees. Geographic datasets are transformed into a suitable projected CRS before measurement. Compact extents prefer a local UTM zone; wider extents use a Lambert Azimuthal Equal Area / Azimuthal Equidistant strategy around the dataset centroid.

## Security and reliability

ZIP extraction blocks path traversal, rejects unsafe symlinks, limits compressed/uncompressed size and file count, and requires Shapefile component files. Upload size and feature-count limits are configurable through environment variables. Invalid files move to `FAILED` with a user-facing error instead of crashing the API.

## Design decisions

FastAPI was selected for typed request/response models and automatic OpenAPI documentation. GeoPandas/Pyogrio/GDAL provide mature format and CRS support instead of maintaining custom parsers. SQLite is the default for easy local execution while SQLAlchemy keeps persistence replaceable. A background worker/queue can be added later for very large datasets.

## Learning and future scope

This project reinforced practical geospatial concepts such as CRS selection, projected-vs-geographic measurement semantics, safe archive extraction, and separation of API, processing, and persistence concerns. Future work includes asynchronous job queues, PostGIS, object storage, pagination/streaming for large feature sets, richer geometry support, observability, authentication/rate limiting, and cloud deployment.

## Tests

```bash
pytest
```

## Docker

```bash
docker compose up --build
```

License: MIT.
