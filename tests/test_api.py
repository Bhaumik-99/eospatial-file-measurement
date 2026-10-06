import io
import zipfile

import geopandas as gpd
from shapely.geometry import Polygon


def make_shapefile_zip() -> bytes:
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as tmp:
        shp = Path(tmp) / "survey.shp"
        gdf = gpd.GeoDataFrame(
            [
                {
                    "name": "plot-a",
                    "geometry": Polygon(
                        [(77, 28), (77.001, 28), (77.001, 28.001), (77, 28.001)]
                    ),
                },
            ],
            crs="EPSG:4326",
        )
        gdf.to_file(shp, engine="pyogrio")
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for path in Path(tmp).glob("survey.*"):
                zf.write(path, arcname=path.name)
        return buf.getvalue()


def test_health(client):
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_upload_shapefile_and_measurements(client):
    payload = make_shapefile_zip()
    response = client.post(
        "/api/files/",
        files={"upload": ("survey.zip", payload, "application/zip")},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["feature_count"] == 1
    assert data["crs"] == "EPSG:4326"
    assert data["status"] == "COMPLETED"

    file_id = data["id"]
    assert client.get(f"/api/files/{file_id}/").status_code == 200

    measurements = client.get(f"/api/files/{file_id}/measurements/")
    assert measurements.status_code == 200
    items = measurements.json()["items"]
    assert items[0]["area_m2"] is not None and items[0]["area_m2"] > 0
    assert items[0]["measurement_crs"] != "EPSG:4326"


def test_invalid_extension(client):
    response = client.post(
        "/api/files/",
        files={"upload": ("survey.txt", b"not geospatial", "text/plain")},
    )
    assert response.status_code == 415


def test_missing_file_returns_422(client):
    response = client.post("/api/files/")
    assert response.status_code == 422
