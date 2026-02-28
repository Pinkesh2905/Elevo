from django.utils.deprecation import MiddlewareMixin
from organizations.models import Membership


class PremiumAccessMiddleware(MiddlewareMixin):
    """
    Attaches premium/organization context to every authenticated request.

    After this middleware runs, these attributes are available:
        request.user_org          — Organization instance or None
        request.user_membership   — Membership instance or None
        request.premium_plan      — SubscriptionPlan instance or None
        request.is_premium        — Boolean (True if user has active premium)
    """

    def process_request(self, request):
        # Set defaults
        request.user_org = None
        request.user_membership = None
        request.premium_plan = None
        request.is_premium = False

        if not request.user.is_authenticated:
            return

        # Find user's active membership with a valid subscription
        membership = (
            Membership.objects
            .filter(
                user=request.user,
                is_active=True,
                organization__is_active=True,
                organization__subscription__status='ACTIVE',
            )
            .select_related(
                'organization',
                'organization__subscription',
                'organization__subscription__plan',
            )
            .first()
        )

        if membership:
            sub = membership.organization.subscription
            if sub.is_valid:
                request.user_membership = membership
                request.user_org = membership.organization
                request.premium_plan = sub.plan
                request.is_premium = True
        else:
            # Check for personal subscription
            try:
                sub = request.user.personal_subscription
                if sub.is_valid:
                    request.premium_plan = sub.plan
                    request.is_premium = True
            except Exception:
                pass
