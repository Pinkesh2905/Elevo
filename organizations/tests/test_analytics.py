"""
Analytics-specific tests for the buyer-ready analytics features.
"""

from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone

from organizations.models import (
    Organization,
    Membership,
    Subscription,
    SubscriptionPlan,
)
from organizations.analytics import (
    compute_org_kpis,
    compute_weak_topics,
    compute_student_table,
    compute_risk_flags,
    compute_cohort_comparison,
    RISK_THRESHOLDS,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _create_plan(name="FREE", max_students=10, **kwargs):
    defaults = {
        "display_name": name.title(),
        "price_monthly": 0,
        "max_students": max_students,
        "max_problems": -1,
        "max_aptitude_daily": -1,
        "max_interviews_monthly": -1,
        "target_type": "ORGANIZATION",
    }
    defaults.update(kwargs)
    return SubscriptionPlan.objects.create(name=name, **defaults)


def _create_org(admin_user, name="Analytics Org", plan=None):
    org = Organization.objects.create(
        name=name, admin=admin_user, email=admin_user.email
    )
    plan = plan or _create_plan()
    Subscription.objects.create(
        organization=org,
        plan=plan,
        status="ACTIVE",
        start_date=timezone.now(),
        end_date=timezone.now() + timedelta(days=30),
    )
    Membership.objects.create(user=admin_user, organization=org, role="OWNER")
    return org


def _add_member(org, user, role="STUDENT"):
    return Membership.objects.create(user=user, organization=org, role=role)


# ===========================================================================
# Analytics Engine Tests
# ===========================================================================

class AnalyticsKPITests(TestCase):
    """Test KPI computation with empty and populated data."""

    def setUp(self):
        self.owner = User.objects.create_user("an_owner", "anown@test.com", "pass")
        self.stu1 = User.objects.create_user("an_stu1", "stu1@test.com", "pass")
        self.stu2 = User.objects.create_user("an_stu2", "stu2@test.com", "pass")
        self.org = _create_org(self.owner, "Analytics Org")
        _add_member(self.org, self.stu1)
        _add_member(self.org, self.stu2)

    def test_empty_org_returns_zero_kpis(self):
        empty_owner = User.objects.create_user("empty_o", "eo@test.com", "pass")
        empty_org = _create_org(empty_owner, "Empty Org",
                                plan=_create_plan(name="E2", max_students=10))
        # Remove the owner membership to simulate truly empty
        Membership.objects.filter(organization=empty_org).delete()
        kpis = compute_org_kpis(empty_org)
        self.assertEqual(kpis["active_members"], 0)
        self.assertEqual(kpis["readiness_score"], 0)

    def test_kpis_return_expected_keys(self):
        kpis = compute_org_kpis(self.org)
        expected_keys = {
            "active_members", "attempt_rate", "completion_rate",
            "avg_aptitude_score", "avg_interview_score", "readiness_score",
            "aptitude_attempts", "aptitude_completed",
            "coding_submissions", "coding_accepted",
            "interview_sessions", "interview_completed",
        }
        self.assertEqual(set(kpis.keys()), expected_keys)

    def test_kpis_active_members_count(self):
        kpis = compute_org_kpis(self.org)
        self.assertEqual(kpis["active_members"], 3)  # owner + 2 students


class StudentTableTests(TestCase):

    def setUp(self):
        self.owner = User.objects.create_user("st_owner", "stow@test.com", "pass")
        self.stu = User.objects.create_user("st_stu", "ststu@test.com", "pass")
        self.org = _create_org(self.owner, "Table Org")
        _add_member(self.org, self.stu)

    def test_returns_all_members(self):
        students = compute_student_table(self.org)
        usernames = {s["username"] for s in students}
        self.assertIn("st_owner", usernames)
        self.assertIn("st_stu", usernames)

    def test_each_row_has_expected_fields(self):
        students = compute_student_table(self.org)
        required_fields = {
            "user_id", "username", "full_name", "email", "role",
            "joined_at", "quizzes_taken", "avg_aptitude_score",
            "problems_solved", "problems_attempted",
            "interviews_done", "avg_interview_score",
            "readiness_score", "risk_level", "risk_meta",
        }
        for s in students:
            self.assertTrue(required_fields.issubset(set(s.keys())), f"Missing fields in {s.keys()}")


class RiskFlagTests(TestCase):

    def test_at_risk_threshold(self):
        rows = [{"readiness_score": 10}]
        compute_risk_flags(rows)
        self.assertEqual(rows[0]["risk_level"], "at_risk")

    def test_needs_attention_threshold(self):
        rows = [{"readiness_score": 50}]
        compute_risk_flags(rows)
        self.assertEqual(rows[0]["risk_level"], "needs_attention")

    def test_on_track_threshold(self):
        rows = [{"readiness_score": 70}]
        compute_risk_flags(rows)
        self.assertEqual(rows[0]["risk_level"], "on_track")

    def test_strong_threshold(self):
        rows = [{"readiness_score": 90}]
        compute_risk_flags(rows)
        self.assertEqual(rows[0]["risk_level"], "strong")

    def test_boundary_values(self):
        rows = [
            {"readiness_score": 0},
            {"readiness_score": 40},
            {"readiness_score": 60},
            {"readiness_score": 80},
            {"readiness_score": 100},
        ]
        compute_risk_flags(rows)
        self.assertEqual(rows[0]["risk_level"], "at_risk")
        self.assertEqual(rows[1]["risk_level"], "needs_attention")
        self.assertEqual(rows[2]["risk_level"], "on_track")
        self.assertEqual(rows[3]["risk_level"], "strong")
        self.assertEqual(rows[4]["risk_level"], "strong")


class CohortComparisonTests(TestCase):

    def setUp(self):
        self.owner = User.objects.create_user("coh_own", "coh@test.com", "pass")
        self.org = _create_org(self.owner, "Cohort Org")

    def test_returns_expected_structure(self):
        result = compute_cohort_comparison(self.org, days=30)
        self.assertIn("current", result)
        self.assertIn("previous", result)
        self.assertIn("deltas", result)
        self.assertIn("aptitude_attempts", result["current"])
        self.assertIn("coding_submissions", result["current"])
        self.assertIn("interview_sessions", result["current"])


class WeakTopicsTests(TestCase):

    def setUp(self):
        self.owner = User.objects.create_user("wt_own", "wt@test.com", "pass")
        self.org = _create_org(self.owner, "Weak Org")

    def test_returns_list(self):
        topics = compute_weak_topics(self.org)
        self.assertIsInstance(topics, list)

    def test_limit_parameter(self):
        topics = compute_weak_topics(self.org, limit=5)
        self.assertLessEqual(len(topics), 5)


# ===========================================================================
# View Tests
# ===========================================================================

class AnalyticsViewTests(TestCase):

    def setUp(self):
        self.client = Client()
        self.owner = User.objects.create_user("av_owner", "av@test.com", "pass")
        self.student = User.objects.create_user("av_stu", "avs@test.com", "pass")
        self.org = _create_org(self.owner, "View Org")
        _add_member(self.org, self.student)

    def test_analytics_page_accessible_by_owner(self):
        self.client.login(username="av_owner", password="pass")
        resp = self.client.get(reverse("organizations:org_analytics"))
        self.assertEqual(resp.status_code, 200)

    def test_analytics_page_blocked_for_student(self):
        self.client.login(username="av_stu", password="pass")
        resp = self.client.get(reverse("organizations:org_analytics"))
        # Should redirect (decorator blocks STUDENT role)
        self.assertIn(resp.status_code, [302, 403])

    def test_csv_export_returns_csv(self):
        self.client.login(username="av_owner", password="pass")
        resp = self.client.get(reverse("organizations:export_analytics_csv"))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp["Content-Type"], "text/csv")
        content = resp.content.decode()
        self.assertIn("Student", content)
        self.assertIn("Readiness Score", content)

    def test_csv_export_has_correct_row_count(self):
        self.client.login(username="av_owner", password="pass")
        resp = self.client.get(reverse("organizations:export_analytics_csv"))
        lines = resp.content.decode().strip().split("\n")
        # Header + 2 members (owner + student)
        self.assertEqual(len(lines), 3)

    def test_pdf_export_returns_html(self):
        self.client.login(username="av_owner", password="pass")
        resp = self.client.get(reverse("organizations:export_analytics_pdf"))
        self.assertEqual(resp.status_code, 200)
        self.assertIn("Analytics Report", resp.content.decode())

    def test_unauthenticated_redirected(self):
        resp = self.client.get(reverse("organizations:org_analytics"))
        self.assertEqual(resp.status_code, 302)
