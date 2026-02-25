from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages as django_messages


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
    Decorator that restricts a view to organization admins only.
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')
        membership = getattr(request, 'user_membership', None)
        org = getattr(request, 'user_org', None)
        is_org_admin = (
            (membership and membership.role == 'ORG_ADMIN') or
            (org and org.admin == request.user)
        )
        if not is_org_admin:
            django_messages.error(request, "You do not have admin access to this organization.")
            return redirect('home')
        return view_func(request, *args, **kwargs)
    return wrapper


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
