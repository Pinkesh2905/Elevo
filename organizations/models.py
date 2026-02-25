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
        ('PRO', 'Pro'),
        ('ENTERPRISE', 'Enterprise'),
    ]

    name = models.CharField(max_length=20, choices=PLAN_CHOICES, unique=True)
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
    name = models.CharField(max_length=200, help_text="Organization name")
    slug = models.SlugField(max_length=200, unique=True, blank=True)
    logo = models.ImageField(upload_to='org_logos/', blank=True, null=True)
    description = models.TextField(blank=True, help_text="Brief description of the organization")
    website = models.URLField(blank=True)
    email = models.EmailField(blank=True, help_text="Organization contact email")

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
        Organization, on_delete=models.CASCADE, related_name='subscription'
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

    class Meta:
        verbose_name = "Subscription"
        verbose_name_plural = "Subscriptions"

    def __str__(self):
        return f"{self.organization.name} — {self.plan.display_name} ({self.status})"

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
        ('MEMBER', 'Member'),
        ('ORG_ADMIN', 'Org Admin'),
    ]

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='org_memberships'
    )
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name='memberships'
    )
    role = models.CharField(max_length=15, choices=ROLE_CHOICES, default='MEMBER')
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


class OrgInvitation(models.Model):
    """
    Email-based invitation for a user to join an organization.
    """
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('ACCEPTED', 'Accepted'),
        ('EXPIRED', 'Expired'),
    ]

    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name='invitations'
    )
    email = models.EmailField(help_text="Invitee's email address")
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
        return f"Invite {self.email} → {self.organization.name} ({self.status})"

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
