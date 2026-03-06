"""
Tenant Isolation Test Suite for Multi-Tenant Hardening.

Tests cover:
1. Data boundary enforcement (org-scoped queries)
2. Role hierarchy & permission checks
3. Membership management (add/remove/change roles)
4. Domain verification
5. CSV bulk invite/import
6. Middleware (PremiumAccessMiddleware)
7. Invitation email boundary
"""

from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase, RequestFactory, Client
from django.urls import reverse
from django.utils import timezone

from organizations.models import (
    Organization,
    Membership,
    OrgInvitation,
    OrganizationAuditLog,
    Subscription,
    SubscriptionPlan,
)
from organizations.tenant import (
    get_org_user_ids,
    scope_queryset_to_org,
    assert_org_membership,
)
from organizations.decorators import (
    ROLE_HIERARCHY,
    has_minimum_role,
    can_manage_members,
    can_view_analytics,
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


def _create_org(admin_user, name="Test Org", plan=None, **kwargs):
    org = Organization.objects.create(
        name=name, admin=admin_user, email=admin_user.email, **kwargs
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


# ===================================================================
# 1. Tenant Query Scoping Tests
# ===================================================================

class TenantQueryScopingTests(TestCase):
    """Verify that tenant.py scoping utilities enforce data boundaries."""

    def setUp(self):
        self.owner_a = User.objects.create_user("owner_a", "a@orga.com", "pass")
        self.owner_b = User.objects.create_user("owner_b", "b@orgb.com", "pass")
        self.student_a = User.objects.create_user("stu_a", "sa@orga.com", "pass")
        self.student_b = User.objects.create_user("stu_b", "sb@orgb.com", "pass")

        self.org_a = _create_org(self.owner_a, "Org A")
        self.org_b = _create_org(self.owner_b, "Org B",
                                 plan=_create_plan(name="STARTER", max_students=10))
        _add_member(self.org_a, self.student_a)
        _add_member(self.org_b, self.student_b)

    def test_get_org_user_ids_returns_only_org_members(self):
        ids_a = set(get_org_user_ids(self.org_a))
        ids_b = set(get_org_user_ids(self.org_b))
        self.assertIn(self.owner_a.pk, ids_a)
        self.assertIn(self.student_a.pk, ids_a)
        self.assertNotIn(self.student_b.pk, ids_a)
        self.assertNotIn(self.owner_a.pk, ids_b)

    def test_scope_queryset_filters_by_org(self):
        # Using User itself as a trivial queryset with user field = pk
        all_users = User.objects.all()
        scoped = scope_queryset_to_org(all_users, self.org_a, user_field="pk")
        self.assertIn(self.owner_a, scoped)
        self.assertIn(self.student_a, scoped)
        self.assertNotIn(self.student_b, scoped)

    def test_scope_queryset_none_when_org_is_none(self):
        result = scope_queryset_to_org(User.objects.all(), None, user_field="pk")
        self.assertEqual(result.count(), 0)

    def test_assert_org_membership_passes_for_member(self):
        try:
            assert_org_membership(self.student_a, self.org_a)
        except PermissionError:
            self.fail("assert_org_membership raised PermissionError unexpectedly")

    def test_assert_org_membership_fails_for_non_member(self):
        with self.assertRaises(PermissionError):
            assert_org_membership(self.student_b, self.org_a)


# ===================================================================
# 2. Role Hierarchy Tests
# ===================================================================

class RoleHierarchyTests(TestCase):
    """Test role hierarchy helpers in decorators.py."""

    def setUp(self):
        self.owner = User.objects.create_user("owner", "o@test.com", "pass")
        self.admin = User.objects.create_user("admin", "a@test.com", "pass")
        self.trainer = User.objects.create_user("trainer", "t@test.com", "pass")
        self.student = User.objects.create_user("student", "s@test.com", "pass")

        self.org = _create_org(self.owner, "Role Org")
        self.m_admin = _add_member(self.org, self.admin, "ADMIN")
        self.m_trainer = _add_member(self.org, self.trainer, "TRAINER")
        self.m_student = _add_member(self.org, self.student, "STUDENT")
        self.m_owner = Membership.objects.get(user=self.owner, organization=self.org)

    def test_hierarchy_values(self):
        self.assertGreater(ROLE_HIERARCHY["OWNER"], ROLE_HIERARCHY["ADMIN"])
        self.assertGreater(ROLE_HIERARCHY["ADMIN"], ROLE_HIERARCHY["TRAINER"])
        self.assertGreater(ROLE_HIERARCHY["TRAINER"], ROLE_HIERARCHY["STUDENT"])

    def test_has_minimum_role_owner_has_all(self):
        for role in ("STUDENT", "TRAINER", "ADMIN", "OWNER"):
            self.assertTrue(has_minimum_role(self.m_owner, role))

    def test_has_minimum_role_student_only_student(self):
        self.assertTrue(has_minimum_role(self.m_student, "STUDENT"))
        self.assertFalse(has_minimum_role(self.m_student, "TRAINER"))
        self.assertFalse(has_minimum_role(self.m_student, "ADMIN"))
        self.assertFalse(has_minimum_role(self.m_student, "OWNER"))

    def test_can_manage_members_returns_correct(self):
        self.assertTrue(can_manage_members(self.m_owner))
        self.assertTrue(can_manage_members(self.m_admin))
        self.assertFalse(can_manage_members(self.m_trainer))
        self.assertFalse(can_manage_members(self.m_student))

    def test_can_view_analytics_returns_correct(self):
        self.assertTrue(can_view_analytics(self.m_owner))
        self.assertTrue(can_view_analytics(self.m_admin))
        self.assertTrue(can_view_analytics(self.m_trainer))
        self.assertFalse(can_view_analytics(self.m_student))

    def test_has_minimum_role_none_membership(self):
        self.assertFalse(has_minimum_role(None, "STUDENT"))

    def test_legacy_role_normalized(self):
        self.m_student.role = "MEMBER"
        self.m_student.save()
        # normalized_role should map MEMBER -> STUDENT
        self.assertTrue(has_minimum_role(self.m_student, "STUDENT"))
        self.assertFalse(has_minimum_role(self.m_student, "TRAINER"))


# ===================================================================
# 3. View-Level Permission Tests
# ===================================================================

class ViewPermissionTests(TestCase):
    """Integration tests for role-restricted views."""

    def setUp(self):
        self.client = Client()
        self.owner = User.objects.create_user("owner", "o@test.com", "pass")
        self.admin = User.objects.create_user("admin", "a@test.com", "pass")
        self.trainer = User.objects.create_user("trainer", "t@test.com", "pass")
        self.student = User.objects.create_user("student", "s@test.com", "pass")
        self.outsider = User.objects.create_user("outsider", "x@test.com", "pass")

        self.org = _create_org(self.owner, "ViewPerm Org")
        self.m_admin = _add_member(self.org, self.admin, "ADMIN")
        self.m_trainer = _add_member(self.org, self.trainer, "TRAINER")
        self.m_student = _add_member(self.org, self.student, "STUDENT")

    def test_change_role_by_owner_succeeds(self):
        self.client.login(username="owner", password="pass")
        url = reverse("organizations:change_member_role", args=[self.m_student.pk])
        resp = self.client.post(url, {"role": "TRAINER"})
        self.m_student.refresh_from_db()
        self.assertEqual(self.m_student.role, "TRAINER")
        self.assertEqual(resp.status_code, 302)

    def test_change_role_by_student_forbidden(self):
        self.client.login(username="student", password="pass")
        url = reverse("organizations:change_member_role", args=[self.m_trainer.pk])
        resp = self.client.post(url, {"role": "STUDENT"})
        self.m_trainer.refresh_from_db()
        # Student shouldn't have permission — role unchanged
        self.assertEqual(self.m_trainer.role, "TRAINER")

    def test_admin_cannot_promote_to_admin(self):
        self.client.login(username="admin", password="pass")
        url = reverse("organizations:change_member_role", args=[self.m_student.pk])
        resp = self.client.post(url, {"role": "ADMIN"})
        self.m_student.refresh_from_db()
        self.assertEqual(self.m_student.role, "STUDENT")

    def test_owner_can_promote_to_admin(self):
        self.client.login(username="owner", password="pass")
        url = reverse("organizations:change_member_role", args=[self.m_student.pk])
        resp = self.client.post(url, {"role": "ADMIN"})
        self.m_student.refresh_from_db()
        self.assertEqual(self.m_student.role, "ADMIN")

    def test_transfer_ownership(self):
        self.client.login(username="owner", password="pass")
        url = reverse("organizations:transfer_ownership", args=[self.m_admin.pk])
        resp = self.client.post(url)
        self.m_admin.refresh_from_db()
        self.assertEqual(self.m_admin.role, "OWNER")
        self.org.refresh_from_db()
        self.assertEqual(self.org.admin, self.admin)

    def test_non_owner_cannot_transfer_ownership(self):
        self.client.login(username="admin", password="pass")
        url = reverse("organizations:transfer_ownership", args=[self.m_student.pk])
        resp = self.client.post(url)
        self.m_student.refresh_from_db()
        self.assertNotEqual(self.m_student.role, "OWNER")

    def test_outsider_cannot_access_dashboard(self):
        self.client.login(username="outsider", password="pass")
        resp = self.client.get(reverse("organizations:dashboard"))
        # Should redirect (302) because middleware won't find membership
        self.assertIn(resp.status_code, [302, 403])


# ===================================================================
# 4. Domain Verification Tests
# ===================================================================

class DomainVerificationTests(TestCase):
    """Test domain verification flow."""

    def setUp(self):
        self.client = Client()
        self.owner = User.objects.create_user("dv_owner", "owner@college.edu", "pass")
        self.org = _create_org(
            self.owner, "Domain Org",
            verified_domain="college.edu",
        )

    def test_matching_domain_verifies(self):
        self.client.login(username="dv_owner", password="pass")
        resp = self.client.post(reverse("organizations:verify_domain"))
        self.org.refresh_from_db()
        self.assertTrue(self.org.is_domain_verified)
        self.assertEqual(self.org.onboarding_step, "DOMAIN_VERIFIED")

    def test_mismatched_domain_fails(self):
        self.owner.email = "owner@other.com"
        self.owner.save()
        self.client.login(username="dv_owner", password="pass")
        resp = self.client.post(reverse("organizations:verify_domain"))
        self.org.refresh_from_db()
        self.assertFalse(self.org.is_domain_verified)

    def test_no_domain_configured_fails(self):
        self.org.verified_domain = ""
        self.org.save()
        self.client.login(username="dv_owner", password="pass")
        resp = self.client.post(reverse("organizations:verify_domain"))
        self.org.refresh_from_db()
        self.assertFalse(self.org.is_domain_verified)


# ===================================================================
# 5. CSV Bulk Invite Tests
# ===================================================================

class CSVBulkInviteTests(TestCase):
    """Test CSV bulk invite functionality."""

    def setUp(self):
        self.client = Client()
        self.owner = User.objects.create_user("csv_owner", "csv@test.com", "pass")
        self.org = _create_org(self.owner, "CSV Org")

    def _upload_csv(self, csv_content):
        from django.core.files.uploadedfile import SimpleUploadedFile
        csv_file = SimpleUploadedFile("test.csv", csv_content.encode("utf-8"), content_type="text/csv")
        self.client.login(username="csv_owner", password="pass")
        return self.client.post(
            reverse("organizations:bulk_invite_students"),
            {"csv_file": csv_file},
        )

    def test_valid_csv_creates_invitations(self):
        csv_data = "email,role\nstu1@test.com,STUDENT\nstu2@test.com,TRAINER\n"
        resp = self._upload_csv(csv_data)
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(OrgInvitation.objects.filter(organization=self.org).count(), 2)

    def test_invalid_email_skipped(self):
        csv_data = "email,role\nbad-email,STUDENT\ngood@test.com,STUDENT\n"
        resp = self._upload_csv(csv_data)
        self.assertEqual(OrgInvitation.objects.filter(organization=self.org).count(), 1)

    def test_duplicate_email_skipped(self):
        csv_data = "email,role\ndup@test.com,STUDENT\ndup@test.com,STUDENT\n"
        resp = self._upload_csv(csv_data)
        self.assertEqual(OrgInvitation.objects.filter(organization=self.org, email="dup@test.com").count(), 1)

    def test_member_limit_enforced(self):
        # Plan limited to 2 members (owner is 1, so only 1 more slot)
        plan = _create_plan(name="TINY", max_students=2)
        sub = Subscription.objects.get(organization=self.org)
        sub.plan = plan
        sub.save()

        # Pre-create users so bulk import auto-adds them as members
        User.objects.create_user("s1", "s1@test.com", "pass")
        User.objects.create_user("s2", "s2@test.com", "pass")
        User.objects.create_user("s3", "s3@test.com", "pass")

        csv_data = "email,role\ns1@test.com,STUDENT\ns2@test.com,STUDENT\ns3@test.com,STUDENT\n"
        resp = self._upload_csv(csv_data)
        # Only 1 should be added (owner=1 member, limit=2, so 1 slot)
        new_members = Membership.objects.filter(
            organization=self.org, is_active=True
        ).exclude(user=self.owner).count()
        self.assertEqual(new_members, 1)

    def test_existing_user_auto_added_as_member(self):
        User.objects.create_user("existing", "existing@test.com", "pass")
        csv_data = "email,role\nexisting@test.com,TRAINER\n"
        resp = self._upload_csv(csv_data)
        self.assertTrue(
            Membership.objects.filter(
                organization=self.org, user__email="existing@test.com", role="TRAINER"
            ).exists()
        )

    def test_onboarding_step_advances(self):
        self.org.onboarding_step = "DOMAIN_VERIFIED"
        self.org.save()
        csv_data = "email,role\nnew@test.com,STUDENT\n"
        resp = self._upload_csv(csv_data)
        self.org.refresh_from_db()
        self.assertEqual(self.org.onboarding_step, "MEMBERS_INVITED")

    def test_invalid_role_defaults_to_student(self):
        csv_data = "email,role\nuser@test.com,SUPERADMIN\n"
        resp = self._upload_csv(csv_data)
        inv = OrgInvitation.objects.filter(organization=self.org, email="user@test.com").first()
        self.assertIsNotNone(inv)
        self.assertEqual(inv.role, "STUDENT")

    def test_no_csv_shows_error(self):
        self.client.login(username="csv_owner", password="pass")
        resp = self.client.post(reverse("organizations:bulk_invite_students"))
        self.assertEqual(resp.status_code, 302)


# ===================================================================
# 6. Middleware Tests
# ===================================================================

class MiddlewareTests(TestCase):
    """Test PremiumAccessMiddleware attaches correct request attributes."""

    def setUp(self):
        self.client = Client()
        self.owner = User.objects.create_user("mw_owner", "mw@test.com", "pass")
        self.org = _create_org(self.owner, "MW Org")
        self.non_member = User.objects.create_user("nomem", "no@test.com", "pass")

    def test_member_gets_org_context(self):
        self.client.login(username="mw_owner", password="pass")
        resp = self.client.get(reverse("organizations:dashboard"))
        # Should not redirect to login (user is authenticated + has org)
        # A 200 means context is attached (dashboard rendered)
        self.assertIn(resp.status_code, [200, 302])

    def test_non_member_has_no_org_context(self):
        self.client.login(username="nomem", password="pass")
        resp = self.client.get(reverse("organizations:dashboard"))
        # Should redirect because middleware doesn't set user_org
        self.assertEqual(resp.status_code, 302)


# ===================================================================
# 7. Invitation Email Boundary Tests
# ===================================================================

class InvitationBoundaryTests(TestCase):
    """Test that invitation acceptance enforces email matching."""

    def setUp(self):
        self.client = Client()
        self.owner = User.objects.create_user("inv_owner", "inv@test.com", "pass")
        self.org = _create_org(self.owner, "Invite Org")

        self.invite = OrgInvitation.objects.create(
            organization=self.org,
            email="target@test.com",
            role="STUDENT",
            invited_by=self.owner,
            expires_at=timezone.now() + timedelta(days=7),
        )

    def test_correct_email_accepts(self):
        user = User.objects.create_user("target", "target@test.com", "pass")
        self.client.login(username="target", password="pass")
        resp = self.client.get(reverse("organizations:join_org", args=[self.invite.token]))
        self.invite.refresh_from_db()
        self.assertEqual(self.invite.status, "ACCEPTED")
        self.assertTrue(Membership.objects.filter(user=user, organization=self.org).exists())

    def test_wrong_email_rejected(self):
        user = User.objects.create_user("wrong", "wrong@test.com", "pass")
        self.client.login(username="wrong", password="pass")
        resp = self.client.get(reverse("organizations:join_org", args=[self.invite.token]))
        self.invite.refresh_from_db()
        self.assertEqual(self.invite.status, "PENDING")
        self.assertFalse(Membership.objects.filter(user=user, organization=self.org).exists())

    def test_expired_invite_rejected(self):
        self.invite.expires_at = timezone.now() - timedelta(days=1)
        self.invite.save()
        user = User.objects.create_user("late", "target@test.com", "pass")
        self.client.login(username="late", password="pass")
        resp = self.client.get(reverse("organizations:join_org", args=[self.invite.token]))
        self.invite.refresh_from_db()
        self.assertEqual(self.invite.status, "EXPIRED")

    def test_invite_role_propagated_to_membership(self):
        self.invite.role = "TRAINER"
        self.invite.save()
        user = User.objects.create_user("trainer_inv", "target@test.com", "pass")
        self.client.login(username="trainer_inv", password="pass")
        resp = self.client.get(reverse("organizations:join_org", args=[self.invite.token]))
        mem = Membership.objects.filter(user=user, organization=self.org).first()
        self.assertIsNotNone(mem)
        self.assertEqual(mem.role, "TRAINER")


# ===================================================================
# 8. CSV Template Download Test
# ===================================================================

class CSVTemplateDownloadTests(TestCase):

    def setUp(self):
        self.client = Client()
        self.owner = User.objects.create_user("tmpl_owner", "tmpl@test.com", "pass")
        self.org = _create_org(self.owner, "Template Org")

    def test_download_returns_csv(self):
        self.client.login(username="tmpl_owner", password="pass")
        resp = self.client.get(reverse("organizations:csv_template_download"))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp["Content-Type"], "text/csv")
        self.assertIn("email", resp.content.decode())


# ===================================================================
# 9. Audit Log Tests
# ===================================================================

class AuditLogTests(TestCase):
    """Verify audit trail is generated for key actions."""

    def setUp(self):
        self.client = Client()
        self.owner = User.objects.create_user("aud_owner", "aud@test.com", "pass")
        self.student = User.objects.create_user("aud_stu", "stuaud@test.com", "pass")
        self.org = _create_org(self.owner, "Audit Org")
        self.m_student = _add_member(self.org, self.student)

    def test_role_change_creates_audit(self):
        self.client.login(username="aud_owner", password="pass")
        url = reverse("organizations:change_member_role", args=[self.m_student.pk])
        self.client.post(url, {"role": "TRAINER"})
        self.assertTrue(
            OrganizationAuditLog.objects.filter(
                organization=self.org,
                action="MEMBERSHIP_ROLE_CHANGED",
            ).exists()
        )

    def test_ownership_transfer_creates_audit(self):
        admin = User.objects.create_user("aud_admin", "audadm@test.com", "pass")
        m_admin = _add_member(self.org, admin, "ADMIN")
        self.client.login(username="aud_owner", password="pass")
        url = reverse("organizations:transfer_ownership", args=[m_admin.pk])
        self.client.post(url)
        self.assertTrue(
            OrganizationAuditLog.objects.filter(
                organization=self.org,
                action="MEMBERSHIP_ROLE_CHANGED",
            ).exists()
        )
