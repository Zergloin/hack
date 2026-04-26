import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app
from app.services.report_service import PDFExportError


class ReportApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.client = TestClient(app)
        cls.client.__enter__()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.client.__exit__(None, None, None)

    def _create_report(self) -> int:
        response = self.client.post(
            "/api/v1/reports/generate",
            json={
                "report_type": "comprehensive",
                "region_id": 1,
                "year_from": 2017,
                "year_to": 2022,
            },
        )
        self.assertEqual(response.status_code, 200)
        return response.json()["id"]

    def test_export_pdf_returns_pdf_stream(self) -> None:
        report_id = self._create_report()
        fake_pdf = b"%PDF-1.7\n%fake\n"

        with patch("app.api.reports.export_pdf", return_value=fake_pdf):
            response = self.client.get(f"/api/v1/reports/{report_id}/export?format=pdf")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["content-type"], "application/pdf")
        self.assertTrue(response.content.startswith(b"%PDF"))

    def test_export_pdf_returns_503_when_generation_fails(self) -> None:
        report_id = self._create_report()

        with patch(
            "app.api.reports.export_pdf",
            side_effect=PDFExportError("PDF export is unavailable"),
        ):
            response = self.client.get(f"/api/v1/reports/{report_id}/export?format=pdf")

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["detail"], "PDF export is unavailable")

    def test_generated_report_contains_forecast_context(self) -> None:
        response = self.client.post(
            "/api/v1/reports/generate",
            json={
                "report_type": "forecast",
                "region_id": 1,
                "year_from": 2017,
                "year_to": 2022,
            },
        )

        self.assertEqual(response.status_code, 200)
        content = response.json()["content_markdown"]
        self.assertIn("Прогноз модели", content)
        self.assertIn("2027", content)
