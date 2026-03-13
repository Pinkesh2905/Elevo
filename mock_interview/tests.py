from types import SimpleNamespace

from django.contrib.auth.models import User
from django.test import TestCase

from . import views
from .models import MockInterviewSession


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

    def test_response_quality_extended(self):
        answer = (
            "I successfully designed and built a robust REST API using Django Rest Framework "
            "because the project required high scalability to handle a large user base. "
            "The final result was a significant 30% improvement in latency for 10,000 active users."
        )
        q = views._response_quality(answer)
        # Score breakdown: Length(20) + Action(25) + Metric(25) + Structure(20) = 90
        self.assertGreaterEqual(q["quality_score"], 80)
        self.assertTrue(q["has_action_language"])
        self.assertTrue(q["has_metrics"])
        self.assertTrue(q["has_structure"])

    def test_generate_personalized_opening_fallback(self):
        from unittest.mock import patch
        session = SimpleNamespace(
            job_role="Software Engineer",
            parsed_resume_data={"interview_track": "technical"},
        )
        # Force the AI call to fail to test the fallback string
        with patch.object(views.AI, 'text', side_effect=RuntimeError("AI Error")):
            opening = views._generate_personalized_opening(session)
            self.assertIn("Elevo", opening)
            self.assertIn("Software Engineer", opening)
            self.assertIn("technical", opening.lower())

    def test_band_transition_promote_and_demote(self):
        self.assertEqual(views._band_transition("standard", [62, 78, 82]), "advanced")
        self.assertEqual(views._band_transition("standard", [40, 44]), "foundation")
        self.assertEqual(views._band_transition("advanced", [80, 83]), "advanced")

    def test_score_turn_returns_structured_metrics(self):
        session = SimpleNamespace(
            key_skills="python,sql",
            parsed_resume_data={"resume_profile": {"skills": ["python"], "tools_tech": ["sql"]}},
        )
        payload = views._score_turn(
            session,
            "I designed and optimized the API because latency was high, and reduced it by 35% for 20k users.",
        )
        self.assertIn("turn_score", payload)
        self.assertIn("communication_score", payload)
        self.assertIn("technical_score", payload)
        self.assertIn("confidence_score", payload)
        self.assertIsInstance(payload["skill_tags"], list)
        self.assertGreaterEqual(payload["turn_score"], 0)
        self.assertLessEqual(payload["turn_score"], 100)

    def test_assign_starting_band_defaults(self):
        user = User.objects.create_user(username="band_user", password="x")
        band, confidence = views._assign_starting_band(user, "technical", ats_score=86)
        self.assertIn(band, {"foundation", "standard", "advanced"})
        self.assertGreaterEqual(confidence, 0)

    def test_difficulty_for_question_by_band(self):
        session = SimpleNamespace(current_band="foundation", performance_band="foundation")
        self.assertEqual(views._difficulty_for_question(session, "technical-core"), "easy")
        session.current_band = "advanced"
        self.assertEqual(views._difficulty_for_question(session, "technical-core"), "hard")

    def test_extract_explicit_skills_from_resume_section(self):
        text = (
            "SKILLS:\nPython, Django, SQL, Docker\n"
            "Projects:\nBuilt APIs for placement platform."
        )
        skills = views._extract_explicit_skills(text)
        self.assertIn("python", skills)
        self.assertIn("django", skills)
        self.assertIn("sql", skills)

    def test_infer_target_role_from_resume_evidence(self):
        text = "Worked on React frontend and TypeScript UI modules, collaborated with design."
        role, confidence = views._infer_target_role(text, "", ["react", "typescript", "javascript"])
        self.assertIn(role, {"Frontend Developer", "Full Stack Developer"})
        self.assertGreaterEqual(confidence, 55)

    def test_extract_jd_requirements(self):
        jd = (
            "Required Skills: Python, Django, SQL, Docker\n"
            "Must have experience with REST API development."
        )
        reqs = views._extract_jd_requirements(jd)
        self.assertIn("python", reqs)
        self.assertIn("django", reqs)
        self.assertIn("sql", reqs)

    def test_compute_jd_fit_insights(self):
        profile = {
            "skills": ["python", "django", "sql"],
            "tools_tech": ["docker"],
            "preferred_role": "Backend Developer",
        }
        jd = "Backend Developer role. Required: Python, Django, SQL, AWS"
        fit = views._compute_jd_fit_insights(profile, jd, role_hint="Backend Developer", track="technical")
        self.assertIsNotNone(fit)
        self.assertGreaterEqual(fit["fit_score"], 60)
        self.assertIn("aws", fit["missing_skills"])


class MockInterviewModelDefaultsTests(TestCase):
    def test_new_session_defaults(self):
        user = User.objects.create_user(username="session_defaults", password="x")
        session = MockInterviewSession.objects.create(user=user, job_role="SE", key_skills="python")
        self.assertEqual(session.performance_band, "standard")
        self.assertEqual(session.current_band, "standard")
        self.assertEqual(session.feedback_status, "pending")
