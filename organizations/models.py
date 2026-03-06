from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.utils.text import slugify


class SubscriptionPlan(models.Model):
    """
    Predefined subscription tiers available for organizations.
    """
    PLAN_CHOICES = [
        ('FREE', 'Free'),
        ('STARTER', 'Starter'),
        ('GROWTH', 'Growth'),
        ('ENTERPRISE', 'Enterprise'),
        # Legacy plans retained for compatibility with older rows
        ('PRO', 'Pro'),
        ('PERSONAL_PRO', 'Personal Pro'),
    ]

    TARGET_CHOICES = [
        ('INDIVIDUAL', 'Individual'),
        ('ORGANIZATION', 'Organization'),
    ]

    name = models.CharField(max_length=20, choices=PLAN_CHOICES, unique=True)
    target_type = models.CharField(
        max_length=20, 
        choices=TARGET_CHOICES, 
        default='ORGANIZATION'
    )
    display_name = models.CharField(max_length=50, help_text="Human-readable plan name")
    description = models.TextField(blank=True, help_text="Plan description for marketing")
    price_monthly = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        help_text="Monthly price in INR"
    )

    # Limits (-1 means unlimited)
    max_students = models.IntegerField(default=10, help_text="Max students per org. -1 = unlimited")
    max_problems = models.IntegerField(default=10, help_text="Max coding problems accessible. -1 = unlimited")
    max_aptitude_daily = models.IntegerField(default=3, help_text="Max aptitude quizzes per student per day. -1 = unlimited")
    max_interviews_monthly = models.IntegerField(default=0, help_text="Max mock interviews per student per month. -1 = unlimited")

    # Feature flags
    has_editorials = models.BooleanField(default=False, help_text="Access to problem editorials/solutions")
    has_detailed_analytics = models.BooleanField(default=False, help_text="Access to detailed org analytics")
    has_custom_branding = models.BooleanField(default=False, help_text="Custom org branding support")
    has_priority_support = models.BooleanField(default=False, help_text="Priority customer support")

    # AI quota
    ai_tokens_monthly = models.IntegerField(
        default=50000,
        help_text="Max AI tokens per org per month. -1 = unlimited",
    )

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['price_monthly']
        verbose_name = "Subscription Plan"
        verbose_name_plural = "Subscription Plans"

    def __str__(self):
        return f"{self.display_name} (₹{self.price_monthly}/mo)"

    def is_unlimited(self, field):
        """Check if a limit field is set to unlimited (-1)."""
        return getattr(self, field) == -1


class Organization(models.Model):
    """
    Represents a subscribing organization (college, institute, company).
    """
    ONBOARDING_STEPS = [
        ('PENDING', 'Pending'),
        ('DOMAIN_SETUP', 'Domain Setup'),
        ('DOMAIN_VERIFIED', 'Domain Verified'),
        ('MEMBERS_INVITED', 'Members Invited'),
        ('COMPLETE', 'Complete'),
    ]

    name = models.CharField(max_length=200, help_text="Organization name")
    slug = models.SlugField(max_length=200, unique=True, blank=True)
    logo = models.ImageField(upload_to='org_logos/', blank=True, null=True)
    description = models.TextField(blank=True, help_text="Brief description of the organization")
    website = models.URLField(blank=True)
    email = models.EmailField(blank=True, help_text="Organization contact email")
    verified_domain = models.CharField(
        max_length=120,
        blank=True,
        help_text="Primary verified email domain for this organization (e.g. college.edu).",
    )
    is_domain_verified = models.BooleanField(default=False)
    domain_verification_token = models.CharField(max_length=64, blank=True)
    onboarding_step = models.CharField(
        max_length=20,
        choices=ONBOARDING_STEPS,
        default='PENDING',
        help_text="Current onboarding progress.",
    )

    admin = models.ForeignKey(
        User, on_delete=models.PROTECT, related_name='owned_organizations',
        help_text="Primary admin/owner of this organization"
    )

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        verbose_name = "Organization"
        verbose_name_plural = "Organizations"

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.name)
            slug = base_slug
            counter = 1
            while Organization.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = slug
        super().save(*args, **kwargs)

    @property
    def active_subscription(self):
        """Get the current active subscription, if any."""
        try:
            sub = self.subscription
            if sub.is_valid:
                return sub
        except Subscription.DoesNotExist:
            pass
        return None

    @property
    def member_count(self):
        """Count of active members."""
        return self.memberships.filter(is_active=True).count()

    @property
    def can_add_members(self):
        """Check if org can add more members based on plan limits."""
        sub = self.active_subscription
        if not sub:
            return False
        plan = sub.plan
        if plan.max_students == -1:
            return True
        return self.member_count < plan.max_students

    def has_feature_access(self, feature_field):
        """Check if the active plan has a specific feature flag enabled."""
        sub = self.active_subscription
        if not sub or not sub.is_valid:
            return False
        return getattr(sub.plan, feature_field, False)

    def get_limit(self, limit_field):
        """Get the numeric limit for a specific field from the active plan."""
        sub = self.active_subscription
        if not sub or not sub.is_valid:
            return 0
        return getattr(sub.plan, limit_field, 0)


class Subscription(models.Model):
    """
    Active subscription linking an organization to a plan.
    """
    STATUS_CHOICES = [
        ('ACTIVE', 'Active'),
        ('EXPIRED', 'Expired'),
        ('CANCELLED', 'Cancelled'),
        ('TRIAL', 'Trial'),
    ]

    organization = models.OneToOneField(
        Organization, on_delete=models.CASCADE, related_name='subscription',
        null=True, blank=True
    )
    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name='personal_subscription',
        null=True, blank=True
    )
    plan = models.ForeignKey(
        SubscriptionPlan, on_delete=models.PROTECT, related_name='subscriptions'
    )
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='ACTIVE')

    start_date = models.DateTimeField(default=timezone.now)
    end_date = models.DateTimeField(help_text="When the subscription expires")

    # Payment tracking
    payment_id = models.CharField(
        max_length=255, blank=True,
        help_text="External payment reference (Razorpay/Stripe)"
    )
    auto_renew = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def clean(self):
        from django.core.exceptions import ValidationError
        if self.organization and self.user:
            raise ValidationError("A subscription cannot be linked to both an organization and a user.")
        if not self.organization and not self.user:
            raise ValidationError("A subscription must be linked to either an organization or a user.")

    def save(self, *args, **kwargs):
        if not kwargs.get('update_fields'):
            self.full_clean()
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = "Subscription"
        verbose_name_plural = "Subscriptions"

    def __str__(self):
        target = self.organization.name if self.organization else self.user.username
        return f"{target} — {self.plan.display_name} ({self.status})"

    @property
    def is_valid(self):
        """Check if subscription is currently active and not expired."""
        return self.status == 'ACTIVE' and self.end_date > timezone.now()

    @property
    def days_remaining(self):
        """Days left in current billing period."""
        if not self.is_valid:
            return 0
        delta = self.end_date - timezone.now()
        return max(0, delta.days)

    def expire(self):
        """Mark subscription as expired."""
        self.status = 'EXPIRED'
        self.save(update_fields=['status', 'updated_at'])


class Membership(models.Model):
    """
    Links a user (student) to an organization.
    """
    ROLE_CHOICES = [
        ('OWNER', 'Owner'),
        ('ADMIN', 'Admin'),
        ('TRAINER', 'Trainer'),
        ('STUDENT', 'Student'),
        # Legacy roles kept for compatibility with existing rows
        ('ORG_ADMIN', 'Org Admin (Legacy)'),
        ('MEMBER', 'Member (Legacy)'),
    ]

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='org_memberships'
    )
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name='memberships'
    )
    role = models.CharField(max_length=15, choices=ROLE_CHOICES, default='STUDENT')
    is_active = models.BooleanField(default=True)
    joined_at = models.DateTimeField(auto_now_add=True)
    invited_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='invitations_sent'
    )

    class Meta:
        unique_together = ('user', 'organization')
        verbose_name = "Membership"
        verbose_name_plural = "Memberships"
        indexes = [
            models.Index(fields=['user', 'is_active']),
            models.Index(fields=['organization', 'is_active']),
        ]

    def __str__(self):
        return f"{self.user.username} @ {self.organization.name} ({self.role})"

    @property
    def normalized_role(self):
        """
        Normalize legacy roles to the new role model.
        """
        if self.role == "ORG_ADMIN":
            return "ADMIN"
        if self.role == "MEMBER":
            return "STUDENT"
        return self.role


class OrgInvitation(models.Model):
    """
    Email-based invitation for a user to join an organization.
    """
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('ACCEPTED', 'Accepted'),
        ('EXPIRED', 'Expired'),
    ]
    INVITE_ROLE_CHOICES = [
        ('ADMIN', 'Admin'),
        ('TRAINER', 'Trainer'),
        ('STUDENT', 'Student'),
    ]

    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name='invitations'
    )
    email = models.EmailField(help_text="Invitee's email address")
    role = models.CharField(
        max_length=15,
        choices=INVITE_ROLE_CHOICES,
        default='STUDENT',
        help_text="Role to assign when invitation is accepted.",
    )
    token = models.CharField(max_length=64, unique=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='PENDING')
    invited_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()

    class Meta:
        verbose_name = "Invitation"
        verbose_name_plural = "Invitations"
        ordering = ['-created_at']

    def __str__(self):
        return f"Invite {self.email} → {self.organization.name} ({self.status}, {self.role})"

    @property
    def is_expired(self):
        return timezone.now() > self.expires_at

    def save(self, *args, **kwargs):
        if not self.token:
            import secrets
            self.token = secrets.token_urlsafe(32)
        if not self.expires_at:
            self.expires_at = timezone.now() + timezone.timedelta(days=7)
        super().save(*args, **kwargs)


class OrganizationAuditLog(models.Model):
    """
    Immutable audit trail for organization actions.
    """
    ACTION_CHOICES = [
        ("ORG_CREATED", "Organization Created"),
        ("INVITE_SENT", "Invitation Sent"),
        ("INVITE_CANCELLED", "Invitation Cancelled"),
        ("INVITE_ACCEPTED", "Invitation Accepted"),
        ("MEMBER_REMOVED", "Member Removed"),
        ("MEMBER_LEFT", "Member Left"),
        ("MEMBERSHIP_ROLE_CHANGED", "Membership Role Changed"),
        ("SUBSCRIPTION_PLAN_CHANGED", "Subscription Plan Changed"),
        ("SUBSCRIPTION_CREATED", "Subscription Created"),
    ]

    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="audit_logs",
        null=True,
        blank=True,
    )
    actor = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="org_audit_actions",
    )
    target_user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="org_audit_targets",
    )
    action = models.CharField(max_length=40, choices=ACTION_CHOICES)
    details = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["organization", "created_at"]),
            models.Index(fields=["action", "created_at"]),
        ]

    def __str__(self):
        org_name = self.organization.name if self.organization else "No Org"
        return f"{self.action} @ {org_name} ({self.created_at:%Y-%m-%d %H:%M:%S})"


class OrganizationInterest(models.Model):
    """Tracks students requesting their institution to provide pro access."""
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    feature = models.CharField(max_length=100)
    institution_domain = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'institution_domain', 'feature')

    def __str__(self):
        return f"{self.user.email} interest for {self.institution_domain}"
