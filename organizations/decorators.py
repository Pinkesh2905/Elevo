from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages as django_messages


# ---------------------------------------------------------------------------
# Role hierarchy (higher number = more privilege)
# ---------------------------------------------------------------------------
ROLE_HIERARCHY = {
    "OWNER": 4,
    "ADMIN": 3,
    "TRAINER": 2,
    "STUDENT": 1,
}


def _normalized_role(membership):
    if not membership:
        return None
    if hasattr(membership, "normalized_role"):
        return membership.normalized_role
    if membership.role == "ORG_ADMIN":
        return "ADMIN"
    if membership.role == "MEMBER":
        return "STUDENT"
    return membership.role


def has_minimum_role(membership, min_role):
    """
    Return True if *membership*'s normalized role is at least *min_role*
    in the hierarchy (OWNER > ADMIN > TRAINER > STUDENT).
    """
    role = _normalized_role(membership)
    if role is None:
        return False
    return ROLE_HIERARCHY.get(role, 0) >= ROLE_HIERARCHY.get(min_role, 0)


def can_manage_members(membership):
    """Owner and Admin can manage (add/remove/change) members."""
    return has_minimum_role(membership, "ADMIN")


def can_view_analytics(membership):
    """Owner, Admin, and Trainer can view org analytics."""
    return has_minimum_role(membership, "TRAINER")


def can_create_content(membership):
    """Owner, Admin, and Trainer can create org content."""
    return has_minimum_role(membership, "TRAINER")


def org_member_required(view_func):
    """
    Restrict to any active organization member (any role).
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect("login")
        membership = getattr(request, "user_membership", None)
        if not membership:
            django_messages.error(request, "You are not part of an organization.")
            return redirect("organizations:my_org")
        return view_func(request, *args, **kwargs)
    return wrapper


def org_role_required(*allowed_roles):
    """
    Restrict view by normalized organization role.
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect("login")
            membership = getattr(request, "user_membership", None)
            if not membership:
                django_messages.error(request, "You are not part of an organization.")
                return redirect("organizations:my_org")

            role = _normalized_role(membership)
            if role not in set(allowed_roles):
                django_messages.error(request, "You do not have permission for this organization action.")
                return redirect("organizations:dashboard")
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


def premium_required(view_func):
    """
    Decorator that restricts a view to users with an active premium subscription.
    Redirects to the upgrade page if the user is not premium.
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')
        if not getattr(request, 'is_premium', False):
            django_messages.warning(
                request,
                "This feature requires a premium subscription. "
                "Ask your organization admin to upgrade."
            )
            return redirect('organizations:upgrade_required')
        return view_func(request, *args, **kwargs)
    return wrapper


def premium_feature(feature_flag):
    """
    Decorator that checks if the user's plan has a specific feature enabled.
    
    Usage: @premium_feature('has_editorials')
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect('login')
            plan = getattr(request, 'premium_plan', None)
            if not plan or not getattr(plan, feature_flag, False):
                django_messages.warning(
                    request,
                    "Your current plan does not include this feature. "
                    "Upgrade to unlock it."
                )
                return redirect('organizations:upgrade_required')
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


def org_admin_required(view_func):
    """
    Restrict to organization Owner/Admin roles.
    """
    return org_role_required("OWNER", "ADMIN")(view_func)


def check_premium_limit(limit_field, get_current_usage):
    """
    Decorator factory that checks usage against a plan limit.
    
    Args:
        limit_field: The SubscriptionPlan field name (e.g., 'max_interviews_monthly')
        get_current_usage: A callable(request) → int that returns current usage count
    
    Usage:
        @check_premium_limit('max_interviews_monthly', lambda r: get_interview_count(r.user))
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            plan = getattr(request, 'premium_plan', None)

            # No plan = use free defaults
            if not plan:
                # For non-org users, allow limited free access
                return view_func(request, *args, **kwargs)

            limit = getattr(plan, limit_field, 0)

            # -1 means unlimited
            if limit == -1:
                return view_func(request, *args, **kwargs)

            # Check current usage
            current = get_current_usage(request)
            if current >= limit:
                django_messages.warning(
                    request,
                    f"You've reached your plan's limit for this feature. "
                    f"Ask your organization admin to upgrade for more access."
                )
                return redirect('organizations:upgrade_required')

            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator
