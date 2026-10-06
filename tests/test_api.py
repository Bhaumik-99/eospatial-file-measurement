import io
import tempfile
import time
import zipfile
from pathlib import Path

import geopandas as gpd
from shapely.geometry import Polygon


def make_shapefile_zip() -> bytes:
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


def wait_for_completion(client, file_id: str):
    for _ in range(50):
        details = client.get(f"/api/files/{file_id}/").json()
        if details["status"] != "PROCESSING":
            return details
        time.sleep(0.01)
    return details


def test_health(client):
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok", "storage": "ok"}


def test_request_id_is_returned(client):
    response = client.get("/healthz", headers={"X-Request-ID": "test-request-123"})
    assert response.headers["X-Request-ID"] == "test-request-123"


def test_upload_shapefile_and_measurements(client):
    response = client.post(
        "/api/files/",
        files={"upload": ("survey.zip", make_shapefile_zip(), "application/zip")},
    )
    assert response.status_code == 202
    data = response.json()
    assert data["status"] == "PROCESSING"
    details = wait_for_completion(client, data["id"])
    assert details["status"] == "COMPLETED"
    assert details["feature_count"] == 1
    assert details["crs"] == "EPSG:4326"

    measurements = client.get(f"/api/files/{data['id']}/measurements/?page_size=1")
    assert measurements.status_code == 200
    payload = measurements.json()
    assert payload["total"] == 1
    assert payload["has_next"] is False
    item = payload["items"][0]
    assert item["area_m2"] is not None and item["area_m2"] > 0
    assert item["measurement_crs"] != "EPSG:4326"


def test_measurement_can_omit_geometry(client):
    response = client.post(
        "/api/files/",
        files={"upload": ("survey.zip", make_shapefile_zip(), "application/zip")},
    )
    file_id = response.json()["id"]
    wait_for_completion(client, file_id)
    payload = client.get(
        f"/api/files/{file_id}/measurements/?include_geometry=false"
    ).json()
    assert payload["items"][0]["geometry"] is None


def test_measurement_page_size_is_bounded(client):
    response = client.post(
        "/api/files/",
        files={"upload": ("survey.zip", make_shapefile_zip(), "application/zip")},
    )
    file_id = response.json()["id"]
    wait_for_completion(client, file_id)
    response = client.get(f"/api/files/{file_id}/measurements/?page_size=501")
    assert response.status_code == 422


def test_invalid_extension(client):
    response = client.post(
        "/api/files/",
        files={"upload": ("survey.txt", b"not geospatial", "text/plain")},
    )
    assert response.status_code == 415


def test_invalid_kml_returns_422(client):
    response = client.post(
        "/api/files/",
        files={"upload": ("survey.kml", b"<not-kml>", "application/xml")},
    )
    assert response.status_code == 422


def test_unknown_file_returns_404(client):
    response = client.get("/api/files/does-not-exist/")
    assert response.status_code == 404


def test_delete_file(client):
    response = client.post(
        "/api/files/",
        files={"upload": ("survey.zip", make_shapefile_zip(), "application/zip")},
    )
    file_id = response.json()["id"]
    wait_for_completion(client, file_id)
    delete_response = client.delete(f"/api/files/{file_id}/")
    assert delete_response.status_code == 204
    assert client.get(f"/api/files/{file_id}/").status_code == 404
