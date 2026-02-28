from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_POST
from django.urls import reverse
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
from .models import OrganizationInterest, Organization, Subscription, SubscriptionPlan, Membership, OrgInvitation

@login_required
def request_sponsorship(request):
    """
    Handles students requesting their institution to sponsor a Pro plan.
    """
    feature = request.GET.get('feature', 'Pro Features')
    email = request.user.email
    
    if not email or '@' not in email:
        messages.info(request, "Please update your email in your profile to request sponsorship.")
        return redirect('users:profile')
        
    email_domain = email.split('@')[-1]
    
    # Generic personal email providers
    generic_domains = ['gmail.com', 'yahoo.com', 'outlook.com', 'hotmail.com', 'icloud.com']
    
    if email_domain in generic_domains:
        messages.warning(request, "Institutional sponsorship requires a university or corporate email address.")
        return redirect('users:profile')
    
    # Create or update interest record
    interest, created = OrganizationInterest.objects.get_or_create(
        user=request.user,
        institution_domain=email_domain,
        feature=feature
    )
    
    # Logic to count total interest for this domain
    total_count = OrganizationInterest.objects.filter(institution_domain=email_domain).count()
    
    # In a real app, this could trigger an email to the sales team or placement cell
    messages.success(
        request, 
        f"Interest recorded! {total_count} students from {email_domain} have now requested Pro access. "
        "We'll reach out to your placement cell with a sponsorship proposal."
    )
    
    return redirect('home')


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
    invite = OrgInvitation.objects.create(
        organization=org,
        email=email,
        invited_by=request.user,
        expires_at=timezone.now() + timedelta(days=7),
    )

    # Send invitation email
    from django.core.mail import send_mail
    from django.conf import settings
    
    invite_url = f"http://{settings.DOMAIN_NAME}/org/join/{invite.token}/"
    
    subject = f"Invitation to join {org.name} on Elevo"
    message = (
        f"Hi there!\n\n"
        f"You have been invited by {request.user.get_full_name() or request.user.username} "
        f"to join the organization '{org.name}' on Elevo.\n\n"
        f"Elevo helps students bridge the gap between learning and employment with "
        f"AI-powered mock interviews and targeted practice.\n\n"
        f"Click the link below to accept the invitation and gain access to premium features:\n"
        f"{invite_url}\n\n"
        f"If you don't have an account yet, you'll be asked to create one first.\n"
        f"This link will expire in 7 days.\n\n"
        f"Best,\nThe Elevo Team"
    )
    
    try:
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [email],
            fail_silently=False,
        )
        messages.success(request, f"Invitation sent to {email}!")
    except Exception as e:
        messages.warning(request, f"Invitation record created, but email could not be sent: {str(e)}")

    return redirect('organizations:members')


@login_required
@org_admin_required
def cancel_invitation(request, invite_id):
    """
    Cancel and delete a pending invitation.
    """
    if request.method != 'POST':
        return redirect('organizations:members')
        
    invite = get_object_or_404(OrgInvitation, id=invite_id, organization=request.user_org)
    email = invite.email
    invite.delete()
    
    messages.success(request, f"Invitation to {email} has been cancelled.")
    return redirect('organizations:members')


# --- Join Organization (via invite link) ---
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

    # If not logged in, redirect to signup with pre-filled email and token
    if not request.user.is_authenticated:
        messages.info(request, "Please create an account to join the organization.")
        signup_url = reverse('users:signup')
        return redirect(f"{signup_url}?email={invite.email}&invite_token={token}")

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


def pricing(request):
    """
    Displays pricing plans for both individuals and organizations.
    """
    individual_plans = SubscriptionPlan.objects.filter(target_type='INDIVIDUAL', is_active=True)
    org_plans = SubscriptionPlan.objects.filter(target_type='ORGANIZATION', is_active=True)
    
    return render(request, 'organizations/pricing.html', {
        'individual_plans': individual_plans,
        'org_plans': org_plans,
    })


@login_required
@require_POST
def checkout_individual(request):
    """
    Mock checkout flow for individual premium plans.
    In a real app, this would integrate with a payment gateway.
    """
    plan_name = request.POST.get('plan_name')
    plan = get_object_or_404(SubscriptionPlan, name=plan_name, target_type='INDIVIDUAL')
    
    # Check if user already has an active personal subscription
    existing_sub = Subscription.objects.filter(user=request.user, status='ACTIVE').first()
    if existing_sub and existing_sub.is_valid:
        messages.info(request, f"You already have an active {existing_sub.plan.display_name} subscription.")
        return redirect('users:profile')

    # Create new subscription
    Subscription.objects.create(
        user=request.user,
        plan=plan,
        status='ACTIVE',
        start_date=timezone.now(),
        end_date=timezone.now() + timedelta(days=30),
        payment_id=f"MOCK_PYMT_{secrets.token_hex(8)}",
        auto_renew=True
    )
    
    messages.success(request, f"Successfully upgraded to {plan.display_name}! Your premium features are now active.")
    return redirect('dashboard_redirect')
