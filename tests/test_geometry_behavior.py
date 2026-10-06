import geopandas as gpd
from shapely.geometry import GeometryCollection, Point, Polygon

from app.services.geospatial import ProjectionPlan, _measurement, _projection_plan


def test_unsupported_geometry_is_graceful():
    plan = ProjectionPlan("EPSG:4326", "EPSG:32643", "EPSG:32643")
    area, length, measurement_crs, supported = _measurement(
        GeometryCollection([Point(77, 28)]), "EPSG:4326", plan
    )
    assert area is None
    assert length is None
    assert measurement_crs == "EPSG:4326"
    assert supported is False


def test_geographic_crs_selects_projected_utm():
    gdf = gpd.GeoDataFrame(
        geometry=[Polygon([(77, 28), (77.001, 28), (77.001, 28.001), (77, 28)])],
        crs="EPSG:4326",
    )
    plan = _projection_plan(gdf)
    assert plan.area_crs is not None
    assert plan.area_crs.startswith("EPSG:326")


def test_projected_meter_crs_is_reused():
    gdf = gpd.GeoDataFrame(
        geometry=[Polygon([(0, 0), (100, 0), (100, 100), (0, 0)])],
        crs="EPSG:3857",
    )
    plan = _projection_plan(gdf)
    assert plan.area_crs == "EPSG:3857"
    assert plan.length_crs == "EPSG:3857"


def test_empty_dataset_does_not_crash():
    gdf = gpd.GeoDataFrame(geometry=[], crs="EPSG:4326")
    plan = _projection_plan(gdf)
    assert plan.original_crs == "EPSG:4326"
    assert plan.area_crs is None
