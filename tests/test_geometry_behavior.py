from shapely.geometry import GeometryCollection, Point

from app.services.geospatial import ProjectionPlan, _measurement


def test_unsupported_geometry_is_graceful():
    plan = ProjectionPlan("EPSG:4326", "EPSG:32643", "EPSG:32643")
    area, length, measurement_crs, supported = _measurement(
        GeometryCollection([Point(77, 28)]), "EPSG:4326", plan
    )
    assert area is None
    assert length is None
    assert measurement_crs == "EPSG:4326"
    assert supported is False
