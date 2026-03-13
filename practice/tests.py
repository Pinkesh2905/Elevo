from unittest.mock import Mock, patch

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.utils.text import slugify

from .models import CodeTemplate, Problem, TestCase as ProblemTestCase
from .views import execute_code_jdoodle


class PracticeExecutionTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="alice", password="pass12345")
        self.problem = Problem.objects.create(
            problem_number=1,
            title="Two Sum",
            slug=slugify("1-Two Sum"),
            difficulty="easy",
            description="Find two numbers.",
            created_by=self.user,
            is_active=True,
        )
        ProblemTestCase.objects.create(
            problem=self.problem,
            input_data="[2,7,11,15]\n9",
            expected_output="[0,1]",
            is_sample=True,
            order=1,
        )
        CodeTemplate.objects.create(
            problem=self.problem,
            language="python3",
            template_code="def two_sum(nums, target):\n    return [0, 1]",
        )

    def test_run_code_rejects_unsupported_language(self):
        self.client.login(username="alice", password="pass12345")
        response = self.client.post(
            f"/practice/problem/{self.problem.slug}/run/",
            {"code": "print('ok')", "language": "brainfuck"},
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("Unsupported language", response.json()["error"])

    @override_settings(JDOODLE_CLIENT_ID="id", JDOODLE_CLIENT_SECRET="secret")
    @patch("practice.views.requests.post")
    def test_execute_code_handles_non_json_response(self, mock_post):
        mock_response = Mock(status_code=200, text="<html>bad gateway</html>")
        mock_response.json.side_effect = ValueError("not json")
        mock_post.return_value = mock_response

        result = execute_code_jdoodle("print(1)", "python3", "")

        self.assertEqual(result["output"], "")
        self.assertEqual(result["error"], "Invalid response from code execution service")
        self.assertIn("bad gateway", result["details"])
