from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.http import JsonResponse
from django.utils import timezone
from django.db.models import Q, Count

from .models import Organization, Subscription, SubscriptionPlan, Membership, OrgInvitation
from .decorators import org_admin_required

import secrets
from datetime import timedelta


# --- Org Dashboard ---
@login_required
@org_admin_required
def org_dashboard(request):
    """
    Main dashboard for organization admins.
    Shows member count, subscription info, and usage stats.
    """
    org = request.user_org
    sub = org.active_subscription
    members = org.memberships.filter(is_active=True).select_related('user', 'user__profile')
    pending_invites = org.invitations.filter(status='PENDING', expires_at__gt=timezone.now())

    context = {
        'org': org,
        'subscription': sub,
        'members': members,
        'member_count': members.count(),
        'pending_invites': pending_invites,
        'can_add': org.can_add_members,
    }
    return render(request, 'organizations/dashboard.html', context)


# --- Create Organization ---
@login_required
def create_org(request):
    """
    Create a new organization. The creating user becomes the admin.
    """
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        description = request.POST.get('description', '').strip()
        email = request.POST.get('email', '').strip()
        website = request.POST.get('website', '').strip()

        if not name:
            messages.error(request, "Organization name is required.")
            return render(request, 'organizations/create.html')

        if Organization.objects.filter(name__iexact=name).exists():
            messages.error(request, "An organization with this name already exists.")
            return render(request, 'organizations/create.html')

        # Create org
        org = Organization.objects.create(
            name=name,
            description=description,
            email=email or request.user.email,
            website=website,
            admin=request.user,
        )

        # Create free subscription (30-day trial)
        free_plan = SubscriptionPlan.objects.filter(name='FREE').first()
        if free_plan:
            Subscription.objects.create(
                organization=org,
                plan=free_plan,
                status='ACTIVE',
                start_date=timezone.now(),
                end_date=timezone.now() + timedelta(days=30),
            )

        # Add creator as ORG_ADMIN member
        Membership.objects.create(
            user=request.user,
            organization=org,
            role='ORG_ADMIN',
        )

        messages.success(request, f"Organization '{name}' created successfully! You have a 30-day free trial.")
        return redirect('organizations:dashboard')

    return render(request, 'organizations/create.html')


# --- Manage Members ---
@login_required
@org_admin_required
def manage_members(request):
    """
    List and manage organization members.
    """
    org = request.user_org
    members = org.memberships.filter(is_active=True).select_related('user', 'user__profile')
    pending = org.invitations.filter(status='PENDING', expires_at__gt=timezone.now())

    context = {
        'org': org,
        'members': members,
        'pending_invites': pending,
        'can_add': org.can_add_members,
        'max_students': org.active_subscription.plan.max_students if org.active_subscription else 0,
    }
    return render(request, 'organizations/members.html', context)


# --- Invite Student ---
@login_required
@org_admin_required
def invite_student(request):
    """
    Send an invitation to a student by email.
    """
    if request.method != 'POST':
        return redirect('organizations:members')

    org = request.user_org
    email = request.POST.get('email', '').strip().lower()

    if not email:
        messages.error(request, "Email address is required.")
        return redirect('organizations:members')

    if not org.can_add_members:
        messages.error(request, "Your plan's student limit has been reached. Upgrade to add more members.")
        return redirect('organizations:members')

    # Check if already a member
    if Membership.objects.filter(organization=org, user__email=email, is_active=True).exists():
        messages.warning(request, f"{email} is already a member of your organization.")
        return redirect('organizations:members')

    # Check for existing pending invite
    if OrgInvitation.objects.filter(organization=org, email=email, status='PENDING', expires_at__gt=timezone.now()).exists():
        messages.warning(request, f"An invitation is already pending for {email}.")
        return redirect('organizations:members')

    # Create invitation
    OrgInvitation.objects.create(
        organization=org,
        email=email,
        invited_by=request.user,
        expires_at=timezone.now() + timedelta(days=7),
    )

    messages.success(request, f"Invitation sent to {email}!")
    return redirect('organizations:members')


# --- Join Organization (via invite link) ---
@login_required
def join_org(request, token):
    """
    Accept an organization invitation.
    """
    invite = get_object_or_404(OrgInvitation, token=token)

    if invite.status != 'PENDING':
        messages.error(request, "This invitation has already been used.")
        return redirect('home')

    if invite.is_expired:
        invite.status = 'EXPIRED'
        invite.save(update_fields=['status'])
        messages.error(request, "This invitation has expired.")
        return redirect('home')

    org = invite.organization

    # Check if already a member
    existing = Membership.objects.filter(user=request.user, organization=org).first()
    if existing:
        if existing.is_active:
            messages.info(request, f"You are already a member of {org.name}.")
        else:
            existing.is_active = True
            existing.save(update_fields=['is_active'])
            messages.success(request, f"Welcome back to {org.name}!")
        invite.status = 'ACCEPTED'
        invite.save(update_fields=['status'])
        return redirect('home')

    # Check capacity
    if not org.can_add_members:
        messages.error(request, f"{org.name} has reached its member limit. Contact the organization admin.")
        return redirect('home')

    # Create membership
    Membership.objects.create(
        user=request.user,
        organization=org,
        role='MEMBER',
        invited_by=invite.invited_by,
    )

    invite.status = 'ACCEPTED'
    invite.save(update_fields=['status'])

    messages.success(request, f"You've joined {org.name}! You now have access to premium features.")
    return redirect('home')


# --- Remove Member ---
@login_required
@org_admin_required
def remove_member(request, membership_id):
    """
    Deactivate a member from the organization.
    """
    if request.method != 'POST':
        return redirect('organizations:members')

    membership = get_object_or_404(Membership, id=membership_id, organization=request.user_org)

    if membership.user == request.user_org.admin:
        messages.error(request, "You cannot remove the organization owner.")
        return redirect('organizations:members')

    membership.is_active = False
    membership.save(update_fields=['is_active'])
    messages.success(request, f"{membership.user.username} has been removed from the organization.")
    return redirect('organizations:members')


# --- Leave Organization ---
@login_required
def leave_org(request):
    """
    Student leaves their organization.
    """
    if request.method != 'POST':
        return redirect('home')

    membership = getattr(request, 'user_membership', None)
    if not membership:
        messages.error(request, "You are not a member of any organization.")
        return redirect('home')

    org = membership.organization
    if org.admin == request.user:
        messages.error(request, "As the organization owner, you cannot leave. Transfer ownership first.")
        return redirect('organizations:dashboard')

    membership.is_active = False
    membership.save(update_fields=['is_active'])
    messages.success(request, f"You have left {org.name}.")
    return redirect('home')


# --- Subscription Detail ---
@login_required
@org_admin_required
def subscription_detail(request):
    """
    View current subscription details and upgrade options.
    """
    org = request.user_org
    sub = org.active_subscription
    plans = SubscriptionPlan.objects.filter(is_active=True).order_by('price_monthly')

    context = {
        'org': org,
        'subscription': sub,
        'plans': plans,
        'current_plan': sub.plan if sub else None,
    }
    return render(request, 'organizations/subscription.html', context)


# --- Upgrade Required Page ---
@login_required
def upgrade_required(request):
    """
    Paywall page shown when a premium feature is accessed without subscription.
    """
    plans = SubscriptionPlan.objects.filter(is_active=True).order_by('price_monthly')
    context = {
        'plans': plans,
        'user_org': getattr(request, 'user_org', None),
        'is_premium': getattr(request, 'is_premium', False),
    }
    return render(request, 'organizations/upgrade_required.html', context)


# --- My Organization (student view) ---
@login_required
def my_organization(request):
    """
    Student view of their organization membership.
    """
    membership = getattr(request, 'user_membership', None)

    if not membership:
        # Show available plans / create org page
        plans = SubscriptionPlan.objects.filter(is_active=True).order_by('price_monthly')
        return render(request, 'organizations/no_org.html', {'plans': plans})

    org = membership.organization
    sub = org.active_subscription
    is_admin = (membership.role == 'ORG_ADMIN' or org.admin == request.user)

    if is_admin:
        return redirect('organizations:dashboard')

    context = {
        'org': org,
        'subscription': sub,
        'membership': membership,
    }
    return render(request, 'organizations/my_org.html', context)
