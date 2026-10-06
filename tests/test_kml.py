from textwrap import dedent


def test_upload_kml(client):
    kml = dedent(
        '''<?xml version="1.0" encoding="UTF-8"?>
        <kml xmlns="http://www.opengis.net/kml/2.2">
          <Document>
            <Placemark><name>plot</name><Polygon><outerBoundaryIs><LinearRing><coordinates>
              77.0,28.0,0 77.001,28.0,0 77.001,28.001,0 77.0,28.001,0 77.0,28.0,0
            </coordinates></LinearRing></outerBoundaryIs></Polygon></Placemark>
            <Placemark><name>route</name><LineString><coordinates>
              77.0,28.0,0 77.002,28.002,0
            </coordinates></LineString></Placemark>
          </Document>
        </kml>'''
    ).encode()
    response = client.post(
        "/api/files/",
        files={"upload": ("survey.kml", kml, "application/vnd.google-earth.kml+xml")},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["feature_count"] == 2
    assert data["crs"] == "EPSG:4326"
    items = client.get(f"/api/files/{data['id']}/measurements/").json()["items"]
    assert any(item["area_m2"] is not None for item in items)
    assert any(item["length_m"] is not None for item in items)
