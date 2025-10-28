# users/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from django.contrib.auth import login as auth_login, logout
from django.contrib.auth.models import User
from django.urls import reverse
from django.http import HttpResponse
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.db import transaction
from django.conf import settings

from .models import UserProfile, EmailVerificationToken, PasswordResetToken, EmailChangeToken
from .forms import (
    SignupForm, UserUpdateForm, UserProfileUpdateForm, CustomLoginForm,
    ForgotPasswordForm, OTPVerificationForm, PasswordResetForm, 
    ResendVerificationForm, EmailChangeForm
)
from posts.models import Post, Repost


# --- Role helper functions ---
def is_student(user):
    return user.is_authenticated and hasattr(user, 'profile') and user.profile.role == 'STUDENT'

def is_tutor(user):
    return user.is_authenticated and hasattr(user, 'profile') and user.profile.role == 'TUTOR' and user.profile.is_approved_tutor

def is_admin(user):
    return user.is_authenticated and user.is_superuser


# --- Signup View (Email Verification Removed) ---
def signup(request):
    """
    Handles user registration without email verification.
    Users can login immediately after signup.
    """
    if request.user.is_authenticated:
        return redirect('dashboard_redirect')
    
    if request.method == 'POST':
        form = SignupForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                # Create user and activate immediately
                user = form.save(commit=False)
                user.is_active = True  # Account active immediately
                user.save()

                selected_role = form.cleaned_data.get('role', 'STUDENT')

                # Set up user profile
                if hasattr(user, 'profile'):
                    user.profile.role = selected_role
                    user.profile.is_email_verified = True  # Mark as verified
                    user.profile.save()
                else:
                    UserProfile.objects.create(
                        user=user, 
                        role=selected_role,
                        is_email_verified=True  # Mark as verified
                    )

                # Log the user in immediately
                auth_login(request, user)
                
                messages.success(
                    request, 
                    f"Welcome to MockMate, {user.username}! Your account has been created successfully."
                )
                return redirect('dashboard_redirect')
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = SignupForm()

    return render(request, 'users/signup.html', {'form': form})


# --- Email Verification Views (Keep for manual verification if needed) ---
def verify_email_sent(request):
    """Show confirmation that verification email was sent."""
    return render(request, 'users/verify_email_sent.html')


def verify_email(request, token):
    """Verify email using token from email link."""
    try:
        verification_token = EmailVerificationToken.objects.get(
            token=token, 
            is_used=False
        )
        
        if verification_token.is_expired():
            messages.error(request, "Verification link has expired. Please request a new one.")
            return redirect('users:resend_verification')
        
        # Activate user account
        user = verification_token.user
        user.is_active = True
        user.save()
        
        # Mark profile as email verified
        user.profile.is_email_verified = True
        user.profile.save()
        
        # Mark token as used
        verification_token.is_used = True
        verification_token.save()
        
        messages.success(request, "Your email has been verified successfully! You can now log in.")
        return redirect('login')
        
    except EmailVerificationToken.DoesNotExist:
        messages.error(request, "Invalid verification link.")
        return redirect('users:resend_verification')


def resend_verification(request):
    """Resend email verification."""
    if request.method == 'POST':
        form = ResendVerificationForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']
            try:
                user = User.objects.get(email=email)
                
                # Delete old unused tokens
                EmailVerificationToken.objects.filter(user=user, is_used=False).delete()
                
                # Create new token
                token = EmailVerificationToken.objects.create(user=user)
                token.send_verification_email(request)
                
                messages.success(request, f"Verification email sent to {email}")
                return redirect('users:verify_email_sent')
                
            except User.DoesNotExist:
                messages.error(request, "No account found with this email.")
            except Exception as e:
                messages.error(request, "Failed to send verification email. Please try again later.")
    else:
        form = ResendVerificationForm()
    
    return render(request, 'users/resend_verification.html', {'form': form})


# --- Password Reset Views ---
def forgot_password(request):
    """Request password reset."""
    if request.user.is_authenticated:
        return redirect('dashboard_redirect')
    
    if request.method == 'POST':
        form = ForgotPasswordForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']
            try:
                user = User.objects.get(email=email)
                
                # Delete old unused tokens
                PasswordResetToken.objects.filter(user=user, is_used=False).delete()
                
                # Create new token
                reset_token = PasswordResetToken.objects.create(user=user)
                reset_token.send_reset_email()
                
                # Store token in session for OTP verification
                request.session['reset_token_id'] = reset_token.id
                
                messages.success(request, f"Password reset OTP sent to {email}")
                return redirect('users:verify_otp')
                
            except User.DoesNotExist:
                messages.error(request, "No account found with this email.")
            except Exception as e:
                messages.error(request, "Failed to send reset email. Please try again later.")
    else:
        form = ForgotPasswordForm()
    
    return render(request, 'users/forgot_password.html', {'form': form})


def verify_otp(request):
    """Verify OTP for password reset."""
    if request.user.is_authenticated:
        return redirect('dashboard_redirect')
    
    token_id = request.session.get('reset_token_id')
    if not token_id:
        messages.error(request, "Invalid reset session. Please start over.")
        return redirect('users:forgot_password')
    
    try:
        reset_token = PasswordResetToken.objects.get(id=token_id, is_used=False)
    except PasswordResetToken.DoesNotExist:
        messages.error(request, "Invalid reset token. Please start over.")
        return redirect('users:forgot_password')
    
    if reset_token.is_expired():
        messages.error(request, "Reset token has expired. Please request a new one.")
        return redirect('users:forgot_password')
    
    if reset_token.is_locked():
        messages.error(request, "Too many failed attempts. Please request a new reset.")
        return redirect('users:forgot_password')
    
    if request.method == 'POST':
        form = OTPVerificationForm(request.POST)
        if form.is_valid():
            entered_otp = form.cleaned_data['otp']
            
            if entered_otp == reset_token.otp:
                # OTP correct, proceed to password reset
                request.session['verified_reset_token_id'] = reset_token.id
                return redirect('users:reset_password')
            else:
                reset_token.increment_attempts()
                remaining_attempts = reset_token.MAX_ATTEMPTS - reset_token.attempts
                
                if remaining_attempts > 0:
                    messages.error(request, f"Invalid OTP. {remaining_attempts} attempts remaining.")
                else:
                    messages.error(request, "Too many failed attempts. Please request a new reset.")
                    return redirect('users:forgot_password')
    else:
        form = OTPVerificationForm()
    
    context = {
        'form': form,
        'email': reset_token.user.email,
        'expires_in': (reset_token.expires_at - timezone.now()).total_seconds() / 60,  # minutes
    }
    return render(request, 'users/verify_otp.html', context)


def reset_password(request):
    """Reset password after OTP verification."""
    if request.user.is_authenticated:
        return redirect('dashboard_redirect')
    
    token_id = request.session.get('verified_reset_token_id')
    if not token_id:
        messages.error(request, "Invalid reset session. Please start over.")
        return redirect('users:forgot_password')
    
    try:
        reset_token = PasswordResetToken.objects.get(id=token_id, is_used=False)
    except PasswordResetToken.DoesNotExist:
        messages.error(request, "Invalid reset token. Please start over.")
        return redirect('users:forgot_password')
    
    if reset_token.is_expired():
        messages.error(request, "Reset session has expired. Please start over.")
        return redirect('users:forgot_password')
    
    if request.method == 'POST':
        form = PasswordResetForm(reset_token.user, request.POST)
        if form.is_valid():
            # Save new password
            form.save()
            
            # Mark token as used
            reset_token.is_used = True
            reset_token.save()
            
            # Clear session
            request.session.pop('reset_token_id', None)
            request.session.pop('verified_reset_token_id', None)
            
            messages.success(request, "Password reset successfully! You can now log in with your new password.")
            return redirect('login')
    else:
        form = PasswordResetForm(reset_token.user)
    
    return render(request, 'users/reset_password.html', {'form': form})


# --- Email Change Views ---
@login_required
def change_email(request):
    """Handle email change requests."""
    if request.method == 'POST':
        form = EmailChangeForm(request.user, request.POST)
        if form.is_valid():
            new_email = form.cleaned_data['new_email']
            
            # Delete old unused tokens
            EmailChangeToken.objects.filter(user=request.user, is_used=False).delete()
            
            # Create new token
            change_token = EmailChangeToken.objects.create(
                user=request.user,
                new_email=new_email
            )
            
            try:
                change_token.send_change_email(request)
                messages.success(
                    request, 
                    f"Verification email sent to {new_email}. Please check your email to confirm the change."
                )
                return redirect('users:profile')
            except Exception as e:
                messages.error(request, "Failed to send verification email. Please try again later.")
    else:
        form = EmailChangeForm(request.user)
    
    return render(request, 'users/change_email.html', {'form': form})


def verify_email_change(request, token):
    """Verify email change using token from email link."""
    try:
        change_token = EmailChangeToken.objects.get(token=token, is_used=False)
        
        if change_token.is_expired():
            messages.error(request, "Email change link has expired. Please try again.")
            return redirect('users:profile')
        
        # Check if new email is still available
        if User.objects.filter(email=change_token.new_email).exists():
            messages.error(request, "This email is no longer available.")
            return redirect('users:profile')
        
        # Update user email
        user = change_token.user
        user.email = change_token.new_email
        user.save()
        
        # Mark token as used
        change_token.is_used = True
        change_token.save()
        
        messages.success(request, f"Email successfully changed to {change_token.new_email}")
        return redirect('users:profile')
        
    except EmailChangeToken.DoesNotExist:
        messages.error(request, "Invalid email change link.")
        return redirect('users:profile')


# --- Enhanced Login View (Email Verification Check Removed) ---
def custom_login(request):
    """Custom login view without email verification check."""
    if request.user.is_authenticated:
        return redirect('dashboard_redirect')
    
    if request.method == 'POST':
        form = CustomLoginForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            
            # Login directly without email verification check
            auth_login(request, user)
            messages.success(request, f"Welcome back, {user.username}!")
            
            # Redirect to next URL or dashboard
            next_url = request.GET.get('next', 'dashboard_redirect')
            return redirect(next_url)
        else:
            messages.error(request, "Invalid credentials. Please try again.")
    else:
        form = CustomLoginForm()
    
    return render(request, 'registration/login.html', {'form': form})


# --- Logged-in User Profile View ---
@login_required(login_url='login')
def profile(request):
    """
    Displays and updates the logged-in user's profile.
    """
    user_profile = get_object_or_404(UserProfile, user=request.user)
    is_admin_user = is_admin(request.user)

    if request.method == 'POST':
        user_form = UserUpdateForm(request.POST, instance=request.user)
        profile_form = UserProfileUpdateForm(request.POST, request.FILES, instance=user_profile)

        # Prevent role or approval changes for non-admins
        if not is_admin_user:
            if 'role' in profile_form.fields:
                del profile_form.fields['role']
            if 'is_approved_tutor' in profile_form.fields:
                del profile_form.fields['is_approved_tutor']

        if user_form.is_valid() and profile_form.is_valid():
            # Check if email is being changed
            old_email = request.user.email
            new_email = user_form.cleaned_data.get('email')
            
            if old_email != new_email:
                # Don't save the user form yet, handle email change separately
                profile_form.save()
                messages.info(
                    request, 
                    "To change your email, please use the 'Change Email' option for security."
                )
                return redirect('users:change_email')
            else:
                user_form.save()
                profile_form.save()
                messages.success(request, "Your profile has been updated successfully!")
                return redirect('users:profile')
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        user_form = UserUpdateForm(instance=request.user)
        profile_form = UserProfileUpdateForm(instance=user_profile)

        if not is_admin_user:
            if 'role' in profile_form.fields:
                del profile_form.fields['role']
            if 'is_approved_tutor' in profile_form.fields:
                del profile_form.fields['is_approved_tutor']

    # Fetch logged-in user's posts
    user_posts = Post.objects.filter(author=request.user).order_by('-created_at')

    context = {
        'user_profile': user_profile,
        'user_form': user_form,
        'profile_form': profile_form,
        'is_admin_user': is_admin_user,
        'user_posts': user_posts,
        'is_own_profile': True,
    }

    return render(request, 'users/profile.html', context)


# --- Public User Profile View ---
def public_profile(request, username):
    """Public profile view."""
    user_profile = get_object_or_404(UserProfile, user__username=username)
    
    reposts = Repost.objects.filter(user=user_profile.user).select_related("original_post__author", "original_post__author__profile")
    reposted_posts = [re.original_post for re in reposts]
    
    user_posts = list(Post.objects.filter(author=user_profile.user)) + reposted_posts
    user_posts = sorted(user_posts, key=lambda p: p.created_at, reverse=True)

    context = {
        'user_profile': user_profile,
        'user_posts': user_posts,
        'is_own_profile': request.user == user_profile.user,
        'is_admin_user': request.user.is_staff,
    }
    return render(request, 'users/view_profile.html', context)


# --- Account Management Views ---
@login_required
def account_settings(request):
    """Account settings page."""
    return render(request, 'users/account_settings.html')


@login_required 
def delete_account(request):
    """Delete user account."""
    if request.method == 'POST':
        password = request.POST.get('password')
        if request.user.check_password(password):
            user = request.user
            logout(request)
            user.delete()
            messages.success(request, "Your account has been deleted successfully.")
            return redirect('home')
        else:
            messages.error(request, "Invalid password.")
    
    return render(request, 'users/delete_account.html')


# --- Admin Views ---
@login_required
def admin_users(request):
    """Admin view to manage users."""
    if not is_admin(request.user):
        messages.error(request, "Access denied.")
        return redirect('dashboard_redirect')
    
    users = UserProfile.objects.all().select_related('user').order_by('-created_at')
    
    context = {
        'users': users,
    }
    return render(request, 'users/admin_users.html', context)


@login_required
def toggle_user_status(request, user_id):
    """Toggle user active status (admin only)."""
    if not is_admin(request.user):
        messages.error(request, "Access denied.")
        return redirect('dashboard_redirect')
    
    user = get_object_or_404(User, id=user_id)
    user.is_active = not user.is_active
    user.save()
    
    status = "activated" if user.is_active else "deactivated"
    messages.success(request, f"User {user.username} has been {status}.")
    
    return redirect('users:admin_users')


@login_required
def approve_tutor(request, user_id):
    """Approve tutor status (admin only)."""
    if not is_admin(request.user):
        messages.error(request, "Access denied.")
        return redirect('dashboard_redirect')
    
    user_profile = get_object_or_404(UserProfile, user__id=user_id)
    user_profile.is_approved_tutor = not user_profile.is_approved_tutor
    user_profile.save()
    
    status = "approved" if user_profile.is_approved_tutor else "revoked"
    messages.success(request, f"Tutor status {status} for {user_profile.user.username}.")
    
    return redirect('users:admin_users')


# --- Admin Dashboard Views ---
@staff_member_required
def admin_dashboard(request):
    """
    Admin dashboard showing pending approvals for tutors, problems, and articles.
    """
    # Get pending tutors (tutors who registered but not yet approved)
    pending_tutors = UserProfile.objects.filter(
        role='TUTOR',
        is_approved_tutor=False
    ).select_related('user').order_by('-created_at')
    
    # Initialize empty lists for problems and articles
    pending_problems = []
    pending_articles = []
    
    # Try to import and get inactive problems from practice app
    try:
        from practice.models import Problem
        pending_problems = Problem.objects.filter(
            is_active=False
        ).select_related('created_by').prefetch_related('topics', 'companies').order_by('-created_at')
    except (ImportError, AttributeError) as e:
        # Practice app or Problem model doesn't exist or doesn't have expected fields
        pass
    
    # Try to import and get pending articles from articles app
    try:
        from articles.models import Article
        # Check what field the Article model uses for status
        if hasattr(Article, 'status'):
            pending_articles = Article.objects.filter(status='PENDING').select_related('created_by').order_by('-created_at')
        elif hasattr(Article, 'is_active'):
            pending_articles = Article.objects.filter(is_active=False).select_related('created_by').order_by('-created_at')
        elif hasattr(Article, 'is_published'):
            pending_articles = Article.objects.filter(is_published=False).select_related('created_by').order_by('-created_at')
        else:
            # If no status field, show recent articles
            pending_articles = Article.objects.all().select_related('created_by').order_by('-created_at')[:10]
    except (ImportError, AttributeError) as e:
        # Articles app doesn't exist or Article model doesn't have expected fields
        pass
    
    context = {
        'pending_tutors': pending_tutors,
        'pending_problems': pending_problems,
        'pending_articles': pending_articles,
    }
    
    return render(request, 'users/admin_dashboard.html', context)


@staff_member_required
def admin_approve_tutor(request, user_id):
    """
    Approve a tutor account.
    """
    user = get_object_or_404(User, id=user_id)
    user_profile = user.profile
    
    # Toggle approval status
    user_profile.is_approved_tutor = True
    user_profile.save()
    
    messages.success(request, f'Tutor {user.username} has been approved successfully!')
    return redirect('users:admin_dashboard')