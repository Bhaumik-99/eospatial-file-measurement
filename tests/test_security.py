import io
import zipfile


def test_zip_path_traversal_is_rejected(client):
    payload = io.BytesIO()
    with zipfile.ZipFile(payload, "w") as zf:
        zf.writestr("../../evil.shp", b"x")
    response = client.post(
        "/api/files/",
        files={"upload": ("unsafe.zip", payload.getvalue(), "application/zip")},
    )
    assert response.status_code == 201
    file_id = response.json()["id"]
    details = client.get(f"/api/files/{file_id}/")
    assert details.json()["status"] == "FAILED"
    assert "unsafe path" in details.json()["error_message"].lower()
