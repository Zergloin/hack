import unittest

from fastapi.testclient import TestClient

from app.main import app
from app.services.forecast_service import DEFAULT_FORECAST_MODEL_NAME


class ForecastApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.client = TestClient(app)
        cls.client.__enter__()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.client.__exit__(None, None, None)

    def test_predict_uses_saved_model_artifact(self) -> None:
        municipalities_response = self.client.get("/api/v1/municipalities?limit=1&year=2022")
        self.assertEqual(municipalities_response.status_code, 200)
        municipalities = municipalities_response.json()
        self.assertTrue(municipalities)

        municipality_id = municipalities[0]["id"]
        response = self.client.post(
            "/api/v1/forecast/predict",
            json={"municipality_id": municipality_id, "horizon_years": 5},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()

        self.assertEqual(payload["municipality_id"], municipality_id)
        self.assertEqual(payload["model_name"], DEFAULT_FORECAST_MODEL_NAME)
        self.assertEqual(len(payload["forecast"]), 5)

        historical_years = [point["year"] for point in payload["historical"] if point["population"] is not None]
        self.assertTrue(historical_years)
        expected_years = list(range(max(historical_years) + 1, max(historical_years) + 6))
        self.assertEqual([point["year"] for point in payload["forecast"]], expected_years)

        for point in payload["forecast"]:
            self.assertGreaterEqual(point["predicted_population"], 0)
            self.assertIsNotNone(point["confidence_lower"])
            self.assertIsNotNone(point["confidence_upper"])
            self.assertLessEqual(point["confidence_lower"], point["predicted_population"])
            self.assertGreaterEqual(point["confidence_upper"], point["predicted_population"])

        saved_response = self.client.get(f"/api/v1/forecast/{municipality_id}")
        self.assertEqual(saved_response.status_code, 200)
        self.assertEqual(len(saved_response.json()), 5)
