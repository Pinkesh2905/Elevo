"""
Tenant-scoping utilities for multi-tenant data isolation.

Usage in views:
    from organizations.tenant import get_org_user_ids, scope_queryset_to_org

    # Get all user IDs belonging to an org
    user_ids = get_org_user_ids(org)

    # Filter any queryset with a 'user' FK to only include org members
    qs = scope_queryset_to_org(Submission.objects.all(), org)

    # Custom user field name
    qs = scope_queryset_to_org(InterviewTurn.objects.all(), org, user_field="session__user")
"""

from django.db.models import QuerySet

from organizations.models import Membership


def get_org_user_ids(org):
    """
    Return a flat queryset of User PKs who are active members of *org*.

    This returns a queryset (not a list), so it can be used efficiently
    in sub-queries without fetching all IDs into memory.
    """
    return (
        Membership.objects
        .filter(organization=org, is_active=True)
        .values_list("user_id", flat=True)
    )


def scope_queryset_to_org(queryset, org, user_field="user"):
    """
    Filter *queryset* so only rows belonging to active members of *org*
    are returned.

    Args:
        queryset: Any Django QuerySet with a user FK.
        org: Organization instance to scope to.
        user_field: Name of the FK/field path pointing to auth.User
                    (supports double-underscore paths like "session__user").

    Returns:
        A filtered QuerySet containing only org-member rows.
    """
    if org is None:
        return queryset.none()
    lookup = f"{user_field}__in"
    return queryset.filter(**{lookup: get_org_user_ids(org)})


def assert_org_membership(user, org):
    """
    Raise PermissionError if *user* is not an active member of *org*.
    Useful as a programmatic guard in service-layer code.
    """
    if not Membership.objects.filter(
        user=user, organization=org, is_active=True
    ).exists():
        raise PermissionError(
            f"User {user.pk} is not an active member of organization {org.pk}."
        )
