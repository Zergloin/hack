import json
import unittest

from fastapi.testclient import TestClient

from app.main import app
from app.services.chat_service import THREAD_CONTEXTS


def _collect_sse_text(response_text: str) -> str:
    parts: list[str] = []
    for line in response_text.splitlines():
        if not line.startswith("data: "):
            continue
        payload = line[6:].strip()
        if payload == "[DONE]":
            break
        parts.append(json.loads(payload)["content"])
    return "".join(parts)


class ChatApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.client = TestClient(app)
        cls.client.__enter__()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.client.__exit__(None, None, None)

    def setUp(self) -> None:
        THREAD_CONTEXTS.clear()

    def test_population_question_returns_database_value(self) -> None:
        response = self.client.post(
            "/api/v1/chat/message",
            json={"message": "Какое население было в Татарстане в 2017 году?", "thread_id": "t1"},
        )
        answer = _collect_sse_text(response.text)

        self.assertEqual(response.status_code, 200)
        self.assertIn("2017", answer)
        self.assertIn("Татарстан", answer)
        self.assertIn("3 885 245", answer)

    def test_follow_up_question_uses_thread_context(self) -> None:
        self.client.post(
            "/api/v1/chat/message",
            json={"message": "Какое население было в Татарстане в 2017 году?", "thread_id": "t2"},
        )
        response = self.client.post(
            "/api/v1/chat/message",
            json={"message": "А в 2018?", "thread_id": "t2"},
        )
        answer = _collect_sse_text(response.text)

        self.assertEqual(response.status_code, 200)
        self.assertIn("2018", answer)
        self.assertIn("Татарстан", answer)
        self.assertIn("3 894 276", answer)

    def test_ranking_question_returns_ranked_regions(self) -> None:
        response = self.client.post(
            "/api/v1/chat/message",
            json={"message": "Какие регионы росли быстрее всего?", "thread_id": "t3"},
        )
        answer = _collect_sse_text(response.text)

        self.assertEqual(response.status_code, 200)
        self.assertIn("топ-5 регионов", answer.lower())
        self.assertIn("2018", answer)
        self.assertIn("2023", answer)
        self.assertIn("Республика Ингушетия", answer)

    def test_compare_question_returns_both_regions(self) -> None:
        response = self.client.post(
            "/api/v1/chat/message",
            json={"message": "Сравни Татарстан и Башкортостан по рождаемости за 2019-2022 годы", "thread_id": "t5"},
        )
        answer = _collect_sse_text(response.text)

        self.assertEqual(response.status_code, 200)
        self.assertIn("Татарстан", answer)
        self.assertIn("Башкортостан", answer)
        self.assertIn("2019", answer)
        self.assertIn("2022", answer)
        self.assertIn("10.38", answer)
        self.assertIn("9.84", answer)

    def test_off_topic_question_is_rejected(self) -> None:
        response = self.client.post(
            "/api/v1/chat/message",
            json={"message": "Какая погода в Москве?", "thread_id": "t4"},
        )
        answer = _collect_sse_text(response.text)

        self.assertEqual(response.status_code, 200)
        self.assertIn("Я могу помочь", answer)
        self.assertIn("населении", answer)
