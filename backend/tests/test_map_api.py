import unittest

from fastapi.testclient import TestClient

from app.main import app


class MapApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.client = TestClient(app)
        cls.client.__enter__()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.client.__exit__(None, None, None)

    def test_geojson_change_percent_returns_period_metrics(self) -> None:
        response = self.client.get(
            "/api/v1/map/geojson?level=region&metric=change_percent&year=2022&year_from=2010&year_to=2022"
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["type"], "FeatureCollection")

        matched_feature = next(
            (
                feature
                for feature in payload.get("features", [])
                if isinstance(feature.get("properties", {}).get("db_id"), int)
                and feature.get("properties", {}).get("change_percent") is not None
            ),
            None,
        )
        self.assertIsNotNone(matched_feature)

        properties = matched_feature["properties"]
        self.assertIn("population_start", properties)
        self.assertIn("population_end", properties)
        self.assertIn("change_percent", properties)
        self.assertEqual(properties["year_from"], 2010)
        self.assertEqual(properties["year_to"], 2022)

    def test_geojson_density_returns_population_and_density(self) -> None:
        response = self.client.get(
            "/api/v1/map/geojson?level=region&metric=density&year=2022"
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["type"], "FeatureCollection")

        matched_feature = next(
            (
                feature
                for feature in payload.get("features", [])
                if isinstance(feature.get("properties", {}).get("db_id"), int)
                and feature.get("properties", {}).get("density") is not None
            ),
            None,
        )
        self.assertIsNotNone(matched_feature)

        properties = matched_feature["properties"]
        self.assertIn("population", properties)
        self.assertIn("area_sq_km", properties)
        self.assertIn("density", properties)
        self.assertGreater(properties["population"], 0)
        self.assertGreater(properties["area_sq_km"], 0)
        self.assertGreater(properties["density"], 0)
