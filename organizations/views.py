from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_POST
from django.urls import reverse
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.utils import timezone
from django.db.models import Q, Count
from django.db import transaction

from .models import (
    Organization,
    Subscription,
    SubscriptionPlan,
    Membership,
    OrgInvitation,
    OrganizationAuditLog,
    OrganizationInterest,
)
from .decorators import (
    org_admin_required,
    org_role_required,
    org_member_required,
    has_minimum_role,
    ROLE_HIERARCHY,
)
from .tenant import get_org_user_ids, scope_queryset_to_org

import secrets
import csv
import io
from datetime import timedelta


def _audit(action, organization=None, actor=None, target_user=None, details=None):
    OrganizationAuditLog.objects.create(
        organization=organization,
        actor=actor,
        target_user=target_user,
        action=action,
        details=details or {},
    )


def _normalized_membership_role(membership):
    if not membership:
        return None
    if hasattr(membership, "normalized_role"):
        return membership.normalized_role
    if membership.role == "ORG_ADMIN":
        return "ADMIN"
    if membership.role == "MEMBER":
        return "STUDENT"
    return membership.role


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
    Shows member count, subscription info, usage stats, and org-scoped analytics.
    """
    org = request.user_org
    sub = org.active_subscription
    members = org.memberships.filter(is_active=True).select_related('user', 'user__profile')
    pending_invites = org.invitations.filter(status='PENDING', expires_at__gt=timezone.now())

    # Org-scoped analytics — each block is wrapped in try/except
    # so the dashboard never breaks if an app is missing.
    org_user_ids = get_org_user_ids(org)
    analytics = {}

    try:
        from practice.models import Submission as PracticeSubmission
        analytics['practice_submissions'] = PracticeSubmission.objects.filter(
            user__in=org_user_ids
        ).count()
        analytics['practice_accepted'] = PracticeSubmission.objects.filter(
            user__in=org_user_ids, status='accepted'
        ).count()
    except (ImportError, Exception):
        analytics['practice_submissions'] = 0
        analytics['practice_accepted'] = 0

    try:
        from aptitude.models import AptitudeQuizAttempt
        analytics['aptitude_attempts'] = AptitudeQuizAttempt.objects.filter(
            user__in=org_user_ids
        ).count()
        analytics['aptitude_completed'] = AptitudeQuizAttempt.objects.filter(
            user__in=org_user_ids, status='completed'
        ).count()
    except (ImportError, Exception):
        analytics['aptitude_attempts'] = 0
        analytics['aptitude_completed'] = 0

    try:
        from mock_interview.models import MockInterviewSession
        analytics['interview_sessions'] = MockInterviewSession.objects.filter(
            user__in=org_user_ids
        ).count()
        analytics['interview_completed'] = MockInterviewSession.objects.filter(
            user__in=org_user_ids, status='COMPLETED'
        ).count()
    except (ImportError, Exception):
        analytics['interview_sessions'] = 0
        analytics['interview_completed'] = 0

    context = {
        'org': org,
        'subscription': sub,
        'members': members,
        'member_count': members.count(),
        'pending_invites': pending_invites,
        'can_add': org.can_add_members,
        'analytics': analytics,
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
        verified_domain = request.POST.get('verified_domain', '').strip().lower()

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
            verified_domain=verified_domain,
            is_domain_verified=False,
            domain_verification_token=secrets.token_urlsafe(24),
            onboarding_step='DOMAIN_SETUP' if verified_domain else 'PENDING',
        )

        if verified_domain and request.user.email and "@" in request.user.email:
            user_domain = request.user.email.split("@")[-1].lower()
            if user_domain == verified_domain:
                org.is_domain_verified = True
                org.onboarding_step = 'DOMAIN_VERIFIED'
                org.save(update_fields=["is_domain_verified", "onboarding_step", "updated_at"])

        # Create trial subscription; defaults to FREE, falls back to STARTER.
        trial_plan = (
            SubscriptionPlan.objects.filter(name='FREE').first()
            or SubscriptionPlan.objects.filter(name='STARTER').first()
        )
        if trial_plan:
            Subscription.objects.create(
                organization=org,
                plan=trial_plan,
                status='ACTIVE',
                start_date=timezone.now(),
                end_date=timezone.now() + timedelta(days=30),
            )

        # Add creator as OWNER member
        Membership.objects.create(
            user=request.user,
            organization=org,
            role='OWNER',
        )
        _audit(
            "ORG_CREATED",
            organization=org,
            actor=request.user,
            target_user=request.user,
            details={"name": org.name, "trial_days": 30},
        )

        verify_hint = ""
        if verified_domain and not org.is_domain_verified:
            verify_hint = " Please verify your organization domain from the members page."
        messages.success(request, f"Organization '{name}' created successfully! You have a 30-day free trial.{verify_hint}")
        return redirect('organizations:dashboard')

    return render(request, 'organizations/create.html')


@login_required
@org_admin_required
def manage_members(request):
    """
    List and manage organization members with search and filtering.
    """
    org = request.user_org
    query = request.GET.get('q', '').strip()
    role_filter = request.GET.get('role', '').strip().upper()
    
    members = org.memberships.filter(is_active=True).select_related('user', 'user__profile')
    
    if query:
        members = members.filter(
            Q(user__username__icontains=query) |
            Q(user__email__icontains=query) |
            Q(user__first_name__icontains=query) |
            Q(user__last_name__icontains=query)
        )
        
    if role_filter and role_filter in ['ADMIN', 'TRAINER', 'STUDENT', 'OWNER']:
        members = members.filter(role=role_filter)

    pending = org.invitations.filter(status='PENDING', expires_at__gt=timezone.now())
    if query:
        pending = pending.filter(Q(email__icontains=query))

    context = {
        'org': org,
        'members': members,
        'pending_invites': pending,
        'can_add': org.can_add_members,
        'max_students': org.active_subscription.plan.max_students if org.active_subscription else 0,
        'org_roles': ['ADMIN', 'TRAINER', 'STUDENT'],
        'query': query,
        'role_filter': role_filter,
    }
    return render(request, 'organizations/members.html', context)


@login_required
@org_admin_required
@require_POST
def bulk_member_action(request):
    """
    Handle bulk operations on organization members.
    Actions: 'deactivate', 'change_role', 'resend_invites'.
    """
    org = request.user_org
    action = request.POST.get('action')
    member_ids = request.POST.getlist('member_ids') # list of membership IDs
    invite_ids = request.POST.getlist('invite_ids') # list of invitation IDs
    
    if not (member_ids or invite_ids):
        messages.warning(request, "No members or invitations selected.")
        return redirect('organizations:members')

    actor_role = _normalized_membership_role(request.user_membership)
    count = 0

    if action == 'deactivate':
        memberships = Membership.objects.filter(id__in=member_ids, organization=org, is_active=True)
        for m in memberships:
            # Cannot deactivate owner
            if m.user == org.admin:
                continue
            # Cannot deactivate higher/equal role unless OWNER
            if actor_role != 'OWNER' and ROLE_HIERARCHY.get(_normalized_membership_role(m), 0) >= ROLE_HIERARCHY.get(actor_role, 0):
                continue
                
            m.is_active = False
            m.save(update_fields=['is_active'])
            _audit("MEMBER_REMOVED", organization=org, actor=request.user, target_user=m.user, details={"bulk": True})
            count += 1
        messages.success(request, f"Successfully deactivated {count} member(s).")

    elif action == 'change_role':
        new_role = request.POST.get('new_role', '').strip().upper()
        if new_role not in {'ADMIN', 'TRAINER', 'STUDENT'}:
            messages.error(request, "Invalid role for bulk update.")
        else:
            memberships = Membership.objects.filter(id__in=member_ids, organization=org, is_active=True)
            for m in memberships:
                if m.user == request.user or m.user == org.admin:
                    continue
                if actor_role != 'OWNER' and ROLE_HIERARCHY.get(_normalized_membership_role(m), 0) >= ROLE_HIERARCHY.get(actor_role, 0):
                    continue
                if new_role == 'ADMIN' and actor_role != 'OWNER':
                    continue
                
                m.role = new_role
                m.save(update_fields=['role'])
                count += 1
            messages.success(request, f"Successfully updated roles for {count} member(s).")

    elif action == 'cancel_invites':
        invites = OrgInvitation.objects.filter(id__in=invite_ids, organization=org, status='PENDING')
        count = invites.count()
        invites.delete()
        messages.success(request, f"Successfully cancelled {count} invitation(s).")

    return redirect('organizations:members')


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
    role = request.POST.get('role', 'STUDENT').strip().upper()
    if role not in {'ADMIN', 'TRAINER', 'STUDENT'}:
        role = 'STUDENT'

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

    # Create invitation with role
    invite = OrgInvitation.objects.create(
        organization=org,
        email=email,
        role=role,
        invited_by=request.user,
        expires_at=timezone.now() + timedelta(days=7),
    )
    _audit(
        "INVITE_SENT",
        organization=org,
        actor=request.user,
        details={"email": email, "invite_id": invite.id, "role": role},
    )

    # Send invitation email
    from django.core.mail import send_mail
    from django.conf import settings

    scheme = "https" if request.is_secure() else "http"
    invite_url = f"{scheme}://{settings.DOMAIN_NAME}/org/join/{invite.token}/"

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
    _audit(
        "INVITE_CANCELLED",
        organization=request.user_org,
        actor=request.user,
        details={"email": email, "invite_id": invite.id},
    )
    invite.delete()

    messages.success(request, f"Invitation to {email} has been cancelled.")
    return redirect('organizations:members')


# --- Join Organization (via invite link) ---
def join_org(request, token):
    """
    Accept an organization invitation.
    Uses the role stored on the invitation for the new membership.
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

    # Enforce invitee email boundary
    if request.user.email.lower() != invite.email.lower():
        messages.error(request, "This invitation is linked to a different email account.")
        return redirect('home')

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
        _audit(
            "INVITE_ACCEPTED",
            organization=org,
            actor=request.user,
            target_user=request.user,
            details={"invite_id": invite.id, "existing_membership": True},
        )
        return redirect('home')

    # Check capacity
    if not org.can_add_members:
        messages.error(request, f"{org.name} has reached its member limit. Contact the organization admin.")
        return redirect('home')

    # Create membership with the role from the invitation
    assigned_role = invite.role if invite.role in {'ADMIN', 'TRAINER', 'STUDENT'} else 'STUDENT'
    Membership.objects.create(
        user=request.user,
        organization=org,
        role=assigned_role,
        invited_by=invite.invited_by,
    )

    invite.status = 'ACCEPTED'
    invite.save(update_fields=['status'])
    _audit(
        "INVITE_ACCEPTED",
        organization=org,
        actor=request.user,
        target_user=request.user,
        details={"invite_id": invite.id, "role": assigned_role},
    )

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
    _audit(
        "MEMBER_REMOVED",
        organization=request.user_org,
        actor=request.user,
        target_user=membership.user,
        details={"membership_id": membership.id},
    )
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
    _audit(
        "MEMBER_LEFT",
        organization=org,
        actor=request.user,
        target_user=request.user,
        details={"membership_id": membership.id},
    )
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
    plans = SubscriptionPlan.objects.filter(
        is_active=True,
        target_type='ORGANIZATION'
    ).order_by('price_monthly')

    context = {
        'org': org,
        'subscription': sub,
        'plans': plans,
        'current_plan': sub.plan if sub else None,
    }
    return render(request, 'organizations/subscription.html', context)


@login_required
@org_role_required("OWNER", "ADMIN")
@require_POST
def verify_domain(request):
    """
    Verify organization domain by matching admin email domain.
    Updates the onboarding_step to DOMAIN_VERIFIED on success.
    """
    org = request.user_org
    domain = (org.verified_domain or "").lower().strip()
    if not domain:
        messages.error(request, "No organization domain configured. Update organization profile first.")
        return redirect("organizations:members")

    email = (request.user.email or "").lower().strip()
    if "@" not in email:
        messages.error(request, "Your account must have a valid email to verify domain.")
        return redirect("organizations:members")

    user_domain = email.split("@")[-1]
    if user_domain != domain:
        messages.error(request, f"Domain verification failed. Login with a {domain} email.")
        return redirect("organizations:members")

    org.is_domain_verified = True
    if not org.domain_verification_token:
        org.domain_verification_token = secrets.token_urlsafe(24)
    # Advance onboarding
    if org.onboarding_step in ('PENDING', 'DOMAIN_SETUP'):
        org.onboarding_step = 'DOMAIN_VERIFIED'
    org.save(update_fields=["is_domain_verified", "domain_verification_token", "onboarding_step", "updated_at"])
    _audit(
        "ORG_CREATED",
        organization=org,
        actor=request.user,
        details={"domain_verified": True, "domain": domain},
    )
    messages.success(request, f"Domain {domain} verified successfully.")
    return redirect("organizations:members")


@login_required
@org_admin_required
@require_POST
def bulk_invite_students(request):
    """
    CSV bulk invite/import with optional user auto-creation.
    Expected CSV headers: email, name (optional), role (optional, defaults to STUDENT)
    """
    org = request.user_org
    csv_file = request.FILES.get("csv_file")
    if not csv_file:
        messages.error(request, "Please upload a CSV file.")
        return redirect("organizations:members")

    try:
        content = csv_file.read().decode("utf-8-sig")
    except Exception:
        messages.error(request, "Invalid CSV encoding. Use UTF-8 CSV file.")
        return redirect("organizations:members")

    reader = csv.DictReader(io.StringIO(content))
    # Normalize headers
    headers = {h.lower().strip(): h for h in (reader.fieldnames or [])}
    if "email" not in headers:
        messages.error(request, "CSV must include an 'email' column.")
        return redirect("organizations:members")

    created_count = 0
    skipped_count = 0
    errors = []
    
    # Use atomicity for the batch
    with transaction.atomic():
        for idx, row in enumerate(reader, start=2):
            email = (row.get(headers.get("email", "email")) or "").strip().lower()
            name = (row.get(headers.get("name", "name")) or "").strip()
            role = (row.get(headers.get("role", "role")) or "STUDENT").strip().upper()
            
            if role not in {"ADMIN", "TRAINER", "STUDENT"}:
                role = "STUDENT"

            if not email or "@" not in email:
                skipped_count += 1
                continue

            if not org.can_add_members:
                errors.append(f"Row {idx}: Limit reached.")
                skipped_count += 1
                continue

            # Skip if already a member
            if Membership.objects.filter(organization=org, user__email=email, is_active=True).exists():
                skipped_count += 1
                continue

            user = User.objects.filter(email=email).first()
            
            # If user doesn't exist AND name is provided, auto-create a deactivated user
            # They will set password on first login/activation
            if not user and name:
                username = email.split('@')[0]
                # Ensure unique username
                base_username = username
                counter = 1
                while User.objects.filter(username=username).exists():
                    username = f"{base_username}{counter}"
                    counter += 1
                
                user = User.objects.create(
                    username=username,
                    email=email,
                    first_name=name.split(' ')[0],
                    last_name=' '.join(name.split(' ')[1:]) if ' ' in name else '',
                    is_active=True # Allow login via social/email verification later
                )
                user.set_unusable_password()
                user.save()

            if user:
                # Add directly to org if user exists (or was just created)
                Membership.objects.get_or_create(
                    user=user,
                    organization=org,
                    defaults={'role': role, 'invited_by': request.user}
                )
                _audit("MEMBER_ADDED", organization=org, actor=request.user, target_user=user, details={"bulk": True, "role": role})
                created_count += 1
            else:
                # Create invitation for non-existing user without name
                invite, created = OrgInvitation.objects.get_or_create(
                    organization=org,
                    email=email,
                    status='PENDING',
                    defaults={
                        'role': role,
                        'invited_by': request.user,
                        'expires_at': timezone.now() + timedelta(days=7)
                    }
                )
                if created:
                    _audit("INVITE_SENT", organization=org, actor=request.user, details={"email": email, "role": role, "bulk": True})
                    created_count += 1
                else:
                    skipped_count += 1

    messages.success(request, f"Processed CSV: {created_count} invited/added, {skipped_count} skipped.")
    if errors:
        messages.warning(request, f"Some rows had errors: {', '.join(errors[:5])}")
        
    # Advance onboarding
    if created_count > 0 and org.onboarding_step in ('PENDING', 'DOMAIN_SETUP', 'DOMAIN_VERIFIED'):
        org.onboarding_step = 'MEMBERS_INVITED'
        org.save(update_fields=['onboarding_step', 'updated_at'])
    return redirect("organizations:members")


@login_required
@org_admin_required
@require_POST
def checkout_organization(request):
    """
    Start a simulated checkout flow for organization plans.
    """
    org = request.user_org
    plan_name = request.POST.get('plan_name')
    plan = get_object_or_404(
        SubscriptionPlan,
        name=plan_name,
        target_type='ORGANIZATION',
        is_active=True,
    )

    current_sub = org.active_subscription
    if current_sub and current_sub.plan_id == plan.id:
        messages.info(request, f"{org.name} is already on {plan.display_name}.")
        return redirect('organizations:subscription')

    checkout_ref = f"ORGCHK_{secrets.token_hex(6).upper()}"
    request.session['fake_org_checkout'] = {
        'ref': checkout_ref,
        'plan_id': plan.id,
        'plan_name': plan.display_name,
        'amount': str(plan.price_monthly),
        'currency': 'INR',
        'org_id': org.id,
        'user_id': request.user.id,
        'created_at': timezone.now().isoformat(),
    }
    request.session.modified = True
    return redirect('organizations:fake_org_payment')


@login_required
@org_admin_required
def fake_org_payment(request):
    """
    Simulated payment gateway for organization plan upgrades.
    """
    checkout = request.session.get('fake_org_checkout')
    if not checkout:
        messages.warning(request, "No active organization checkout session found.")
        return redirect('organizations:subscription')

    org = request.user_org
    if checkout.get('org_id') != org.id or checkout.get('user_id') != request.user.id:
        request.session.pop('fake_org_checkout', None)
        messages.error(request, "Invalid checkout session.")
        return redirect('organizations:subscription')

    plan = SubscriptionPlan.objects.filter(
        id=checkout.get('plan_id'),
        target_type='ORGANIZATION',
        is_active=True,
    ).first()
    if not plan:
        request.session.pop('fake_org_checkout', None)
        messages.error(request, "Selected plan is no longer available.")
        return redirect('organizations:subscription')

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'success':
            payment_id = f"ORGMOCKPAY_{checkout.get('ref')}_{secrets.token_hex(4)}"
            sub, created = Subscription.objects.get_or_create(
                organization=org,
                defaults={
                    'plan': plan,
                    'status': 'ACTIVE',
                    'start_date': timezone.now(),
                    'end_date': timezone.now() + timedelta(days=30),
                    'payment_id': payment_id,
                    'auto_renew': True,
                },
            )
            if not created:
                sub.plan = plan
                sub.status = 'ACTIVE'
                sub.start_date = timezone.now()
                sub.end_date = timezone.now() + timedelta(days=30)
                sub.payment_id = payment_id
                sub.auto_renew = True
                sub.save()

            _audit(
                "SUBSCRIPTION_PLAN_CHANGED",
                organization=org,
                actor=request.user,
                details={
                    "new_plan": plan.name,
                    "payment_id": payment_id,
                    "simulated": True,
                },
            )
            request.session.pop('fake_org_checkout', None)
            messages.success(request, f"Payment successful (simulated). {org.name} is now on {plan.display_name}.")
            return redirect('organizations:subscription')

        if action == 'failed':
            messages.error(request, "Payment failed (simulated). Please try again.")
            return redirect('organizations:fake_org_payment')

        if action == 'cancel':
            request.session.pop('fake_org_checkout', None)
            messages.info(request, "Checkout cancelled.")
            return redirect('organizations:subscription')

        messages.error(request, "Invalid payment action.")
        return redirect('organizations:fake_org_payment')

    return render(
        request,
        'organizations/fake_org_payment.html',
        {
            'org': org,
            'plan': plan,
            'checkout': checkout,
        },
    )


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
    is_admin = (_normalized_membership_role(membership) in {"OWNER", "ADMIN"} or org.admin == request.user)

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

    show_individual = True
    show_org = True

    if request.user.is_authenticated and hasattr(request.user, "profile"):
        role = request.user.profile.role
        if role == "STUDENT":
            show_org = False
        elif role == "ORG_ADMIN":
            show_individual = False

    return render(
        request,
        'organizations/pricing.html',
        {
            'individual_plans': individual_plans,
            'org_plans': org_plans,
            'show_individual_plans': show_individual,
            'show_org_plans': show_org,
        },
    )


@login_required
@require_POST
def checkout_individual(request):
    """
    Start a simulated checkout flow for individual premium plans.
    """
    plan_name = request.POST.get('plan_name')
    plan = get_object_or_404(SubscriptionPlan, name=plan_name, target_type='INDIVIDUAL')

    # Check if user already has an active personal subscription
    existing_sub = Subscription.objects.filter(user=request.user, status='ACTIVE').first()
    if existing_sub and existing_sub.is_valid:
        messages.info(request, f"You already have an active {existing_sub.plan.display_name} subscription.")
        return redirect('users:profile')

    checkout_ref = f"CHK_{secrets.token_hex(6).upper()}"
    request.session['fake_checkout'] = {
        'ref': checkout_ref,
        'plan_id': plan.id,
        'plan_name': plan.display_name,
        'amount': str(plan.price_monthly),
        'currency': 'INR',
        'user_id': request.user.id,
        'created_at': timezone.now().isoformat(),
    }
    request.session.modified = True

    return redirect('organizations:fake_payment')


@login_required
def fake_payment(request):
    """
    Simulated payment gateway screen for individual subscriptions.
    """
    checkout = request.session.get('fake_checkout')
    if not checkout or checkout.get('user_id') != request.user.id:
        messages.warning(request, "No active checkout session found.")
        return redirect('organizations:pricing')

    plan = SubscriptionPlan.objects.filter(
        id=checkout.get('plan_id'),
        target_type='INDIVIDUAL',
        is_active=True
    ).first()
    if not plan:
        request.session.pop('fake_checkout', None)
        messages.error(request, "Selected plan is no longer available.")
        return redirect('organizations:pricing')

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'success':
            existing_sub = Subscription.objects.filter(user=request.user, status='ACTIVE').first()
            if existing_sub and existing_sub.is_valid:
                request.session.pop('fake_checkout', None)
                messages.info(request, f"You already have an active {existing_sub.plan.display_name} subscription.")
                return redirect('users:profile')

            payment_id = f"MOCKPAY_{checkout.get('ref', secrets.token_hex(6))}_{secrets.token_hex(4)}"
            Subscription.objects.create(
                user=request.user,
                plan=plan,
                status='ACTIVE',
                start_date=timezone.now(),
                end_date=timezone.now() + timedelta(days=30),
                payment_id=payment_id,
                auto_renew=True
            )
            request.session.pop('fake_checkout', None)
            messages.success(
                request,
                f"Payment successful (simulated). {plan.display_name} is now active."
            )
            return redirect('users:profile')

        if action == 'failed':
            messages.error(request, "Payment failed (simulated). Please try again.")
            return redirect('organizations:fake_payment')

        if action == 'cancel':
            request.session.pop('fake_checkout', None)
            messages.info(request, "Checkout cancelled.")
            return redirect('organizations:pricing')

        messages.error(request, "Invalid payment action.")
        return redirect('organizations:fake_payment')

    return render(
        request,
        'organizations/fake_payment.html',
        {
            'plan': plan,
            'checkout': checkout,
        },
    )


# ===========================================================================
# New views for Multi-Tenant Hardening
# ===========================================================================

@login_required
@org_role_required("OWNER", "ADMIN")
@require_POST
def change_member_role(request, membership_id):
    """
    Change a member's role within the organization.

    Rules:
    - OWNER can change anyone's role (except their own OWNER role via this view).
    - ADMIN can change TRAINER/STUDENT roles but cannot promote to ADMIN or OWNER.
    - Cannot change the role of someone with higher/equal privilege.
    """
    org = request.user_org
    target = get_object_or_404(Membership, id=membership_id, organization=org, is_active=True)
    new_role = request.POST.get("role", "").strip().upper()

    if new_role not in {"ADMIN", "TRAINER", "STUDENT"}:
        messages.error(request, "Invalid role selected.")
        return redirect("organizations:members")

    actor_membership = request.user_membership
    actor_role = _normalized_membership_role(actor_membership)
    target_role = _normalized_membership_role(target)

    # Cannot change own role through this endpoint
    if target.user == request.user:
        messages.error(request, "You cannot change your own role here.")
        return redirect("organizations:members")

    # Cannot change someone with higher/equal hierarchy
    if ROLE_HIERARCHY.get(target_role, 0) >= ROLE_HIERARCHY.get(actor_role, 0):
        messages.error(request, "You cannot change the role of a member with equal or higher privilege.")
        return redirect("organizations:members")

    # Only OWNER can promote to ADMIN
    if new_role == "ADMIN" and actor_role != "OWNER":
        messages.error(request, "Only the organization Owner can promote members to Admin.")
        return redirect("organizations:members")

    old_role = target.role
    target.role = new_role
    target.save(update_fields=["role"])
    _audit(
        "MEMBERSHIP_ROLE_CHANGED",
        organization=org,
        actor=request.user,
        target_user=target.user,
        details={"from": old_role, "to": new_role},
    )
    messages.success(request, f"{target.user.username}'s role changed from {old_role} to {new_role}.")
    return redirect("organizations:members")


@login_required
@org_role_required("OWNER")
@require_POST
def transfer_ownership(request, membership_id):
    """
    Transfer the OWNER role to another member. The current OWNER is
    demoted to ADMIN.
    """
    org = request.user_org
    target = get_object_or_404(Membership, id=membership_id, organization=org, is_active=True)

    if target.user == request.user:
        messages.error(request, "You are already the owner.")
        return redirect("organizations:members")

    # Current owner membership
    owner_membership = request.user_membership

    # Demote current owner to ADMIN
    owner_membership.role = "ADMIN"
    owner_membership.save(update_fields=["role"])

    # Promote target to OWNER
    target.role = "OWNER"
    target.save(update_fields=["role"])

    # Update org.admin FK
    org.admin = target.user
    org.save(update_fields=["admin", "updated_at"])

    _audit(
        "MEMBERSHIP_ROLE_CHANGED",
        organization=org,
        actor=request.user,
        target_user=target.user,
        details={"action": "ownership_transferred", "new_owner": target.user.username},
    )
    messages.success(request, f"Ownership transferred to {target.user.username}. You are now an Admin.")
    return redirect("organizations:members")


@login_required
@org_role_required("OWNER", "ADMIN")
def csv_template_download(request):
    """
    Download a sample CSV template for bulk student invite/import.
    """
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="elevo_invite_template.csv"'
    writer = csv.writer(response)
    writer.writerow(["email", "role", "name"])
    writer.writerow(["student@example.com", "STUDENT", "Jane Doe"])
    writer.writerow(["trainer@example.com", "TRAINER", "John Smith"])
    writer.writerow(["admin@example.com", "ADMIN", "Alice Admin"])
    return response


# ===========================================================================
# Analytics Views
# ===========================================================================

@login_required
@org_role_required("OWNER", "ADMIN", "TRAINER")
def org_analytics(request):
    """
    Premium analytics dashboard for org admins/trainers.
    """
    from .analytics import (
        compute_org_kpis,
        compute_weak_topics,
        compute_student_table,
        compute_cohort_comparison,
    )
    org = request.user_org
    kpis = compute_org_kpis(org)
    weak_topics = compute_weak_topics(org)
    students = compute_student_table(org)
    cohort = compute_cohort_comparison(org, days=30)

    context = {
        "org": org,
        "kpis": kpis,
        "weak_topics": weak_topics,
        "students": students,
        "cohort": cohort,
        "risk_summary": _risk_summary(students),
    }
    return render(request, "organizations/analytics.html", context)


def _risk_summary(students):
    """Count students per risk level for the overview badges."""
    summary = {"at_risk": 0, "needs_attention": 0, "on_track": 0, "strong": 0}
    for s in students:
        level = s.get("risk_level", "at_risk")
        if level in summary:
            summary[level] += 1
    return summary


@login_required
@org_role_required("OWNER", "ADMIN", "TRAINER")
def export_analytics_csv(request):
    """
    Export student analytics as CSV.
    """
    from .analytics import compute_student_table
    org = request.user_org
    students = compute_student_table(org)

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = (
        f'attachment; filename="{org.name.replace(" ", "_")}_analytics.csv"'
    )

    writer = csv.writer(response)
    writer.writerow([
        "Student", "Email", "Role", "Joined",
        "Quizzes Taken", "Avg Aptitude %",
        "Problems Solved", "Problems Attempted",
        "Interviews Done", "Avg Interview %",
        "Readiness Score", "Risk Level",
    ])
    for s in students:
        writer.writerow([
            s["full_name"],
            s["email"],
            s["role"],
            s["joined_at"].strftime("%Y-%m-%d") if s.get("joined_at") else "",
            s["quizzes_taken"],
            s["avg_aptitude_score"],
            s["problems_solved"],
            s["problems_attempted"],
            s["interviews_done"],
            s["avg_interview_score"],
            s["readiness_score"],
            s["risk_meta"]["label"],
        ])
    return response


@login_required
@org_role_required("OWNER", "ADMIN", "TRAINER")
def export_analytics_pdf(request):
    """
    Export analytics as a styled HTML report (print-ready / Save-as-PDF).
    """
    from .analytics import (
        compute_org_kpis,
        compute_weak_topics,
        compute_student_table,
        compute_cohort_comparison,
    )
    org = request.user_org
    kpis = compute_org_kpis(org)
    weak_topics = compute_weak_topics(org)
    students = compute_student_table(org)
    cohort = compute_cohort_comparison(org, days=30)

    context = {
        "org": org,
        "kpis": kpis,
        "weak_topics": weak_topics,
        "students": students,
        "cohort": cohort,
        "risk_summary": _risk_summary(students),
        "generated_at": timezone.now(),
        "is_pdf": True,
    }
    return render(request, "organizations/analytics_report.html", context)


# ===========================================================================
# AI Cost & Latency Dashboard
# ===========================================================================

@login_required
@org_role_required("OWNER", "ADMIN")
def ai_cost_dashboard(request):
    """
    AI cost, latency, and provider health dashboard for org admins.
    """
    from .ai_analytics import (
        compute_ai_cost_summary,
        compute_interview_outcome_metrics,
        compute_latency_stats,
        compute_provider_health,
        compute_quota_usage,
    )
    org = request.user_org
    days = int(request.GET.get("days", 30))
    days = min(max(days, 7), 90)  # clamp 7–90

    cost_summary = compute_ai_cost_summary(org, days=days)
    latency = compute_latency_stats(org, days=days)
    health = compute_provider_health(org, days=days)
    quota = compute_quota_usage(org)
    interview_metrics = compute_interview_outcome_metrics(org, days=days)

    context = {
        "org": org,
        "cost_summary": cost_summary,
        "latency": latency,
        "health": health,
        "quota": quota,
        "interview_metrics": interview_metrics,
        "days": days,
    }
    return render(request, "organizations/ai_dashboard.html", context)
