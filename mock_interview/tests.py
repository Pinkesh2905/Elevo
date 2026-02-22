from types import SimpleNamespace

from django.test import TestCase

from . import views


class MockInterviewHelpersTests(TestCase):
    def test_parse_json_plain(self):
        data = views._parse_json('{"ok": true, "score": 80}')
        self.assertEqual(data["score"], 80)

    def test_parse_json_code_fence(self):
        payload = """```json\n{"items": [1, 2, 3]}\n```"""
        data = views._parse_json(payload)
        self.assertEqual(data["items"], [1, 2, 3])

    def test_coerce_feedback_defaults(self):
        session = SimpleNamespace(job_role="Software Engineer")
        data = views._coerce_feedback({}, session)
        self.assertIn("overall_score", data)
        self.assertIsInstance(data["strengths"], list)

    def test_coerce_feedback_bounds(self):
        session = SimpleNamespace(job_role="Software Engineer")
        raw = {"overall_score": 999, "communication_score": -40, "strengths": "one"}
        data = views._coerce_feedback(raw, session)
        self.assertEqual(data["overall_score"], 100)
        self.assertEqual(data["communication_score"], 0)
        self.assertEqual(data["strengths"], ["one"])

    def test_question_stage(self):
        self.assertEqual(views._question_stage(1), "introduction")
        self.assertEqual(views._question_stage(4), "technical-depth")
        self.assertEqual(views._question_stage(8), "final-evaluation")
        self.assertEqual(views._question_stage(2, track="hr"), "hr-core")

    def test_response_quality(self):
        q = views._response_quality("I built an API and improved latency by 40% for 10k users.")
        self.assertGreaterEqual(q["quality_score"], 60)
        self.assertTrue(q["has_action_language"])
        self.assertTrue(q["has_metrics"])

    def test_repetitive_question_detection(self):
        turns = SimpleNamespace(
            order_by=lambda *args, **kwargs: [
                SimpleNamespace(ai_question="Thanks. Can you tell me about your most significant data project?")
            ]
        )
        is_repeat = views._is_repetitive_question(
            "Great. Could you tell me about your most significant data project?",
            turns,
        )
        self.assertTrue(is_repeat)

    def test_technical_fundamental_question_from_skills(self):
        session = SimpleNamespace(
            key_skills="Python, SQL",
            parsed_resume_data={"resume_profile": {"skills": ["python"]}},
        )
        turns = SimpleNamespace(
            count=lambda: 0,
            order_by=lambda *args, **kwargs: [],
        )
        q = views._technical_fundamental_question(session, turns)
        self.assertTrue("python" in q.lower() or "list and tuple" in q.lower())
